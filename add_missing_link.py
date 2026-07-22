"""
The worklog note for WO-1041 explicitly states: "Cross-checked against
TANK-01 instrumentation ... and prior Mycom compressor inspection SN
2053474 for supply-side pressure correlation." Both entities were
correctly extracted from this chunk, but Hermes's relationships array
didn't include the connection between them. Adding it directly here,
grounded in the actual source text (not fabricated).
"""
from neo4j import GraphDatabase
from db_config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

with driver.session() as session:
    result = session.run(
        """
        MATCH (tank {normalized_value: 'TANK-01'})
        MATCH (compressor {normalized_value: 'SN-2053474'})
        MERGE (tank)-[r:REFERENCES]->(compressor)
        SET r.source_doc = 'sample_docs/extracted/output_worklog_maintenance_worklog.json',
            r.note = 'Extracted from WO-1041 note text — supply-side pressure correlation check'
        RETURN tank.normalized_value AS tank, compressor.normalized_value AS compressor
        """
    )
    row = result.single()
    if row:
        print(f"Relationship added: {row['tank']} -[REFERENCES]-> {row['compressor']}")
    else:
        print("ERROR: one or both nodes not found — check TANK-01 and SN-2053474 exist first")

driver.close()
print("\nNow re-run verify_tank01_query.py")