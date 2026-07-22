"""
Central Neo4j connection config, loaded from .env — never hardcode
credentials directly in scripts. Import NEO4J_URI, NEO4J_USER,
NEO4J_PASSWORD from here everywhere instead.
"""
import os
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.environ.get("NEO4J_URI", "").strip()
NEO4J_USER = os.environ.get("NEO4J_USER", "").strip()
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "").strip()

if not NEO4J_PASSWORD:
    print("WARNING: NEO4J_PASSWORD not set in .env — Neo4j connections will fail.")