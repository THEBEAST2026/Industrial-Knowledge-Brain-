from neo4j import GraphDatabase
from db_config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

with driver.session() as session:
    result = session.run("MATCH (n:Regulation) RETURN n.normalized_value AS val LIMIT 10")
    rows = list(result)
    if not rows:
        print("No Regulation-type nodes found in the graph.")
    else:
        print(f"Found {len(rows)} Regulation node(s):")
        for r in rows:
            print(" ", r["val"])

driver.close()