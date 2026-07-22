"""
Diagnoses the SN-2053474 normalization mismatch between worklog extraction
(likely "SN 2053474" with a space, pulled verbatim from the note text) and
the manually-verified inspection_entities.json ("SN-2053474" with a hyphen),
then merges them into a single canonical node so the cross-document path
resolves.
"""
from neo4j import GraphDatabase
from db_config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD



driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

with driver.session() as session:
    print("Searching for any node containing '2053474'...")
    result = session.run(
        "MATCH (n) WHERE n.normalized_value CONTAINS '2053474' "
        "RETURN labels(n) AS labels, n.normalized_value AS value, n.first_seen_doc AS doc"
    )
    rows = list(result)
    for row in rows:
        print(f"  {row['labels']}: '{row['value']}'  (from: {row['doc']})")

    if len(rows) < 2:
        print("\nOnly found one variant (or none) — the issue may be different than a naming mismatch.")
    else:
        print(f"\nFound {len(rows)} variant(s) — merging them into one canonical node...")
        variant_values = [row["value"] for row in rows]

        # Pick the hyphenated form as canonical (matches your schema convention)
        canonical = next((v for v in variant_values if "-" in v), variant_values[0])
        others = [v for v in variant_values if v != canonical]

        for other in others:
            print(f"  Merging '{other}' -> '{canonical}'")
            # Redirect all relationships from the duplicate node to the
            # canonical one, then delete the duplicate
            session.run(
                """
                MATCH (dup {normalized_value: $other})
                MATCH (canon {normalized_value: $canonical})
                OPTIONAL MATCH (dup)-[r]->(x)
                FOREACH (_ IN CASE WHEN r IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (canon)-[r2:REFERENCES]->(x)
                    SET r2.source_doc = r.source_doc
                )
                OPTIONAL MATCH (y)-[r2]->(dup)
                FOREACH (_ IN CASE WHEN r2 IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (y)-[r3:REFERENCES]->(canon)
                    SET r3.source_doc = r2.source_doc
                )
                DETACH DELETE dup
                """,
                other=other, canonical=canonical
            )
        print("Merge complete.")

driver.close()
print("\nNow re-run verify_tank01_query.py")