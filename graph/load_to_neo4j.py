
import json
from neo4j import GraphDatabase
from db_config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

  


class GraphWriter:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def upsert_entity(self, entity_type, normalized_value, source_doc, chunk_id, raw_value=None):
        
        if entity_type not in {"Equipment", "Permit", "Person", "Regulation",
                                "Incident", "Parameter", "Date"}:
            return
        with self.driver.session() as session:
            session.run(
                f"""MERGE (e:{entity_type} {{normalized_value: $val}})
                    ON CREATE SET e.first_seen_doc = $doc, e.first_seen_chunk = $chunk_id,
                                  e.raw_value = $raw_value
                    SET e.last_seen_doc = $doc, e.last_seen_chunk = $chunk_id""",
                val=normalized_value, doc=source_doc, chunk_id=chunk_id,
                raw_value=raw_value or normalized_value)

    def upsert_relationship(self, from_val, to_val, rel_type, source_doc):
        
        allowed = {"MAINTAINED_BY", "LOCATED_IN", "REFERENCES", "FAILED_ON"}
        if rel_type not in allowed:
            return
        with self.driver.session() as session:
            session.run(
                f"""MATCH (a {{normalized_value: $from_val}}), (b {{normalized_value: $to_val}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    SET r.source_doc = $doc""",
                from_val=from_val, to_val=to_val, doc=source_doc)

    def clear_all(self):
        """Wipe the graph before a fresh load — use during testing only."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")


def guess_entity_type_for_relationship_endpoint(value: str) -> str:
    """
    Relationship endpoints (e.g. 'R. NAIR', 'HW-2291') don't always carry
    their entity_type alongside them in the relationships list, so we
    infer a reasonable label to MERGE against if the node wasn't already
    created by the entities list. Falls back to a generic 'Entity' label.
    """
    if value.replace(" ", "").replace(".", "").isalpha() and " " in value.replace(".", " "):
        return "Person"
    if value.startswith("SN-") or "TANK" in value or "PUMP" in value or "COMPRESSOR" in value:
        return "Equipment"
    if value.startswith("HW-") or value.startswith("CS-"):
        return "Permit"
    return "Entity"


def load_worklog_file(gw: GraphWriter, filepath: str):
    data = json.load(open(filepath))
    for record in data:
        source_doc = record.get("source_doc", filepath)
        chunk_id = record.get("chunk_id", "")
        for e in record.get("entities", []):
            gw.upsert_entity(e["entity_type"], e["normalized_value"], source_doc,
                              chunk_id, e.get("value"))
        for r in record.get("relationships", []):
            
            with gw.driver.session() as session:
                session.run("MERGE (a {normalized_value: $v})", v=r["from"])
                session.run("MERGE (b {normalized_value: $v})", v=r["to"])
            gw.upsert_relationship(r["from"], r["to"], r["type"], source_doc)


def load_pid_file(gw: GraphWriter, filepath: str):
    """
    Handles BOTH shapes:
    - Live extraction output (output_drawing_*.json): flat list of
      {chunk_id, source_doc, entities, relationships} records — same
      shape as load_worklog_file expects.
    - Older manually-verified pid_entities.json: dict with a "chunks" key.
    Auto-detects which shape it's looking at.
    """
    data = json.load(open(filepath))

    if isinstance(data, list):
        
        for record in data:
            source_doc = record.get("source_doc", filepath)
            chunk_id = record.get("chunk_id", "")
            for e in record.get("entities", []):
                gw.upsert_entity(e["entity_type"], e["normalized_value"], source_doc,
                                  chunk_id, e.get("value"))
            for r in record.get("relationships", []):
                with gw.driver.session() as session:
                    session.run("MERGE (a {normalized_value: $v})", v=r["from"])
                    session.run("MERGE (b {normalized_value: $v})", v=r["to"])
                gw.upsert_relationship(r["from"], r["to"], r["type"], source_doc)
        return

   
    source_doc = data.get("source_doc", filepath)
    for chunk in data.get("chunks", []):
        for e in chunk.get("entities", []):
            gw.upsert_entity(e["entity_type"], e["normalized_value"], source_doc,
                              chunk["chunk_id"], e.get("value"))
    for r in data.get("relationships", []):
        with gw.driver.session() as session:
            session.run("MERGE (a {normalized_value: $v})", v=r["from"])
            session.run("MERGE (b {normalized_value: $v})", v=r["to"])
        gw.upsert_relationship(r["from"], r["to"], r["type"], source_doc)


def load_inspection_file(gw: GraphWriter, filepath: str):
    data = json.load(open(filepath))
    for record in data:
        source_doc = record.get("source_doc", filepath)
        chunk_id = record.get("chunk_id", "")
        for e in record.get("entities", []):
            gw.upsert_entity(e["entity_type"], e["normalized_value"], source_doc,
                              chunk_id, e.get("value"))
        for r in record.get("relationships", []):
            with gw.driver.session() as session:
                session.run("MERGE (a {normalized_value: $v})", v=r["from"])
                session.run("MERGE (b {normalized_value: $v})", v=r["to"])
            gw.upsert_relationship(r["from"], r["to"], r["type"], source_doc)


if __name__ == "__main__":
    gw = GraphWriter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    print("Clearing existing graph (testing mode)...")
    gw.clear_all()

    print("Loading worklog entities...")
    load_worklog_file(gw, "sample_docs/extracted/output_worklog_maintenance_worklog.json")

    print("Loading P&ID entities...")
    load_pid_file(gw, "sample_docs/extracted/output_drawing_pid_cropped.json")

    print("Loading inspection report entities...")
    load_inspection_file(gw, "sample_docs/extracted/output_inspection_live.json")

    print("Done. Run the verification query next (see verify_tank01_query.py).")
    gw.close()