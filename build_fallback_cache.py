"""
Builds a clean, structured fallback cache of your proven demo query result.
Run this AFTER confirming verify_tank01_query.py works live. This captures
the actual graph state as JSON + a human-readable summary, so if Neo4j
hiccups during judging, you have something more presentable than a raw
terminal scrollback to show instead.
"""
import json
from datetime import datetime
from neo4j import GraphDatabase
from db_config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

QUERY_NEIGHBORHOOD = """
MATCH (t {normalized_value: 'TANK-01'})-[r]-(neighbor)
RETURN type(r) AS relationship, labels(neighbor) AS neighbor_labels,
       neighbor.normalized_value AS neighbor_value, r.source_doc AS source_document
ORDER BY relationship
"""

QUERY_CROSS_DOC_PATH = """
MATCH path = (t {normalized_value: 'TANK-01'})-[*1..2]-(inspection_node)
WHERE inspection_node.normalized_value = 'SN-2053474'
RETURN [n IN nodes(path) | n.normalized_value] AS path_nodes,
       [r IN relationships(path) | type(r)] AS path_relationships,
       [r IN relationships(path) | r.source_doc] AS source_documents_crossed
"""

with driver.session() as session:
    neighborhood = [dict(r) for r in session.run(QUERY_NEIGHBORHOOD)]
    cross_doc = [dict(r) for r in session.run(QUERY_CROSS_DOC_PATH)]

driver.close()

fallback = {
    "captured_at": datetime.now().isoformat(),
    "demo_question": "What maintenance was performed on TANK-01, and how does it relate to the compressor inspection findings?",
    "answer_summary": (
        "TANK-01 is connected in the knowledge graph to its P&ID instrument "
        "tags (LAL-01, LAH-01, LS-01, LT-01) from the facility drawing, and "
        "directly references compressor inspection SN-2053474 (Mycom "
        "200SUD-HE) based on a maintenance work order (WO-1041) that "
        "cross-checked TANK-01 instrumentation against the compressor's "
        "prior inspection findings for supply-side pressure correlation. "
        "This connects three separate source documents — a maintenance "
        "worklog, a P&ID drawing, and an inspection report — into one "
        "traversable graph."
    ),
    "tank01_neighborhood": neighborhood,
    "cross_document_path": cross_doc,
    "documents_involved": [
        "maintenance_worklog.csv (worklog)",
        "pid_cropped.png (P&ID drawing)",
        "3769_-_Mycom_200SUD-HE_rapport.pdf (inspection report)",
    ],
}

with open("demo_fallback_cache.json", "w") as f:
    json.dump(fallback, f, indent=2)

# Also write a plain-text version that's easy to read on screen during a demo
with open("demo_fallback_readable.txt", "w") as f:
    f.write("=" * 70 + "\n")
    f.write("DEMO FALLBACK — CROSS-DOCUMENT RETRIEVAL PROOF\n")
    f.write("=" * 70 + "\n\n")
    f.write(f"Question: {fallback['demo_question']}\n\n")
    f.write(f"Answer:\n{fallback['answer_summary']}\n\n")
    f.write("-" * 70 + "\n")
    f.write("TANK-01 direct neighborhood:\n")
    for n in neighborhood:
        f.write(f"  TANK-01 -[{n['relationship']}]-> {n['neighbor_value']} "
                 f"({n['neighbor_labels']})  [{n['source_document']}]\n")
    f.write("\n" + "-" * 70 + "\n")
    f.write("Verified cross-document path:\n")
    for p in cross_doc:
        f.write(f"  Path: {' -> '.join(p['path_nodes'])}\n")
        f.write(f"  Relationships: {p['path_relationships']}\n")
        f.write(f"  Source documents crossed: {p['source_documents_crossed']}\n")

print("Saved:")
print("  demo_fallback_cache.json   (structured, for programmatic fallback)")
print("  demo_fallback_readable.txt (plain text, easy to screen-share if needed)")
print(f"\nNeighborhood entries: {len(neighborhood)}")
print(f"Cross-document paths found: {len(cross_doc)}")
if not cross_doc:
    print("\nWARNING: No cross-document path in this capture — re-check before relying on this fallback!")