"""
Schema definition for the Industrial Knowledge Brain graph. This is the
single source of truth for what's a valid traversal — both the planning
prompt (schema_planner.py) and the executor (schema_executor.py) import
this so the constraint check happens in code, not just in the LLM's head.

Matches the entity/relationship types already used across
entity_extractor.py, entity_resolution.py, and load_to_neo4j.py.
"""

ENTITY_TYPES = ["Equipment", "Permit", "Person", "Regulation", "Incident", "Parameter", "Date"]

RELATIONSHIP_TYPES = ["MAINTAINED_BY", "LOCATED_IN", "REFERENCES", "FAILED_ON"]

# Valid (from_type, relationship, to_type) triples. Anything not listed here
# is rejected by the executor even if the planner or a hallucinated Cypher
# query tries to use it — this is the actual constraint enforcement, not
# just a prompt suggestion. Modeled after the source material's example:
# a Pump can have a FlowRate (Equipment -REFERENCES-> Parameter) but never
# a SoftwareVersion (no such relationship/entity type exists in this schema).
VALID_PATHS = {
    ("Equipment", "MAINTAINED_BY", "Person"),
    ("Equipment", "LOCATED_IN", "Equipment"),      # e.g. instrument -> tank
    ("Equipment", "REFERENCES", "Parameter"),
    ("Equipment", "REFERENCES", "Regulation"),
    ("Equipment", "REFERENCES", "Permit"),
    ("Equipment", "FAILED_ON", "Date"),
    ("Equipment", "FAILED_ON", "Incident"),
    ("Permit", "REFERENCES", "Equipment"),
    ("Permit", "REFERENCES", "Regulation"),
    ("Incident", "REFERENCES", "Equipment"),
    ("Incident", "REFERENCES", "Regulation"),
    ("Person", "MAINTAINED_BY", "Equipment"),      # bidirectional in practice
}

# Human-readable schema description for the LLM prompt — this is what
# actually gets injected into the planning call.
def schema_as_prompt_text() -> str:
    lines = ["ENTITY TYPES:"]
    lines += [f"  - {t}" for t in ENTITY_TYPES]
    lines.append("\nVALID RELATIONSHIP PATHS (from_type -[relationship]-> to_type):")
    for frm, rel, to in sorted(VALID_PATHS):
        lines.append(f"  - {frm} -[{rel}]-> {to}")
    lines.append(
        "\nANY path not listed above is INVALID and must not appear in a plan. "
        "For example, Equipment can connect to Parameter (e.g. a Pump has a "
        "FlowRate) but there is no valid path from Equipment to a concept "
        "like 'SoftwareVersion' — that entity type does not exist in this "
        "schema at all, so any plan referencing it must be rejected."
    )
    return "\n".join(lines)


def is_valid_hop(from_type: str, relationship: str, to_type: str) -> bool:
    return (from_type, relationship, to_type) in VALID_PATHS


if __name__ == "__main__":
    print(schema_as_prompt_text())