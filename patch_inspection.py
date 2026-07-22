"""
Patches the already-loaded graph with the manually-verified inspection
report entities (SN-2053474, SN-2053500), since the live extraction got
0 entities from that document. Does NOT clear the graph first — adds to
what's already loaded from the live worklog/P&ID run.
"""
import sys
sys.path.insert(0, "graph")
from load_to_neo4j import GraphWriter, load_inspection_file
from db_config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD



gw = GraphWriter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

print("Patching in manually-verified inspection entities (NOT clearing graph)...")
load_inspection_file(gw, "sample_docs/extracted/inspection_entities.json")
print("Done. Re-run verify_tank01_query.py now.")

gw.close()