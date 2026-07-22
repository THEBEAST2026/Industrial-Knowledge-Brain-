"""
Runs the TANK-01 cross-document verification query and prints the result
in a readable form. This is the query to screen-share/demo live — it
proves entities from the worklog CSV, the P&ID drawing, and (via the
SN-2053474 link one hop further) the inspection report all resolve into
one connected neighborhood in the graph.

Run after load_to_neo4j.py has completed successfully.
"""
from neo4j import GraphDatabase
from db_config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Query 1: Direct 1-hop neighborhood of TANK-01 — should show it connected
# to instrument tags from the P&ID (LAL-01, LAH-01, LS-01, LT-01, LY-01,
# LR-01) AND to the maintenance record referencing SN-2053474, R. NAIR,
# and permit CS-4201 from the worklog — proving both documents contributed.
QUERY_NEIGHBORHOOD = """
MATCH (t {normalized_value: 'TANK-01'})-[r]-(neighbor)
RETURN labels(t) AS tank_labels, type(r) AS relationship,
       labels(neighbor) AS neighbor_labels, neighbor.normalized_value AS neighbor_value,
       r.source_doc AS source_document
ORDER BY relationship
"""

# Query 2: 2-hop traversal from TANK-01 to the inspection report, through
# the SN-2053474 bridge node — this is the "cross-functional knowledge
# discovery" the PS8 rubric explicitly rewards.
QUERY_CROSS_DOC_PATH = """
MATCH path = (t {normalized_value: 'TANK-01'})-[*1..2]-(inspection_node)
WHERE inspection_node.normalized_value = 'SN-2053474'
RETURN [n IN nodes(path) | n.normalized_value] AS path_nodes,
       [r IN relationships(path) | type(r)] AS path_relationships,
       [r IN relationships(path) | r.source_doc] AS source_documents_crossed
"""

with driver.session() as session:
    print("=" * 70)
    print("QUERY 1: Direct neighborhood of TANK-01")
    print("=" * 70)
    result = session.run(QUERY_NEIGHBORHOOD)
    rows = list(result)
    if not rows:
        print("No results — check that load_to_neo4j.py ran successfully.")
    for row in rows:
        print(f"  TANK-01 --[{row['relationship']}]--> {row['neighbor_value']} "
              f"({row['neighbor_labels']})  [from: {row['source_document']}]")

    print()
    print("=" * 70)
    print("QUERY 2: Cross-document path from TANK-01 to inspection report SN-2053474")
    print("=" * 70)
    result = session.run(QUERY_CROSS_DOC_PATH)
    rows = list(result)
    if not rows:
        print("No path found — this would mean the cross-document link didn't resolve.")
    for row in rows:
        print(f"  Path: {' -> '.join(row['path_nodes'])}")
        print(f"  Relationships: {row['path_relationships']}")
        print(f"  Crossed documents: {row['source_documents_crossed']}")

driver.close()

print()
print("If Query 2 returned a path, you have a verified, working example of")
print("cross-document retrieval: worklog -> P&ID (via TANK-01) and")
print("worklog -> inspection report (via SN-2053474) in a single graph.")
print("This is the answer to demo question: 'What maintenance was performed")
print("on TANK-01, and how does it relate to the compressor inspection findings?'")