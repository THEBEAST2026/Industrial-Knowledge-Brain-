"""
Industrial Knowledge Brain — API layer.

Run: uvicorn main:app --reload --port 8000
Docs auto-generated at: http://localhost:8000/docs

Your frontend teammate builds against these endpoints — they don't need
to touch ingestion/retrieval/graph code directly.
"""
import sys
sys.path.insert(0, "ingestion")
sys.path.insert(0, "retrieval")
sys.path.insert(0, "graph")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json

from db_config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from neo4j import GraphDatabase

app = FastAPI(title="Industrial Knowledge Brain API", version="1.0")

# Allow the frontend (running on a different port during dev) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your actual frontend URL before production
    allow_methods=["*"],
    allow_headers=["*"],
)

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ---------- Request/Response models ----------

class EntityNeighborhoodResponse(BaseModel):
    entity: str
    neighbors: list[dict]


class CrossDocPathResponse(BaseModel):
    found: bool
    paths: list[dict]


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    route: str
    result: dict


# ---------- Health check ----------

@app.get("/health")
def health_check():
    try:
        with driver.session() as session:
            session.run("RETURN 1")
        return {"status": "ok", "neo4j": "connected"}
    except Exception as e:
        return {"status": "degraded", "neo4j_error": str(e)}


# ---------- Entity neighborhood (used for graph visualization in frontend) ----------

@app.get("/entity/{normalized_value}/neighborhood", response_model=EntityNeighborhoodResponse)
def get_entity_neighborhood(normalized_value: str):
    """
    Returns all direct neighbors of a given entity — e.g. GET /entity/TANK-01/neighborhood
    Frontend can use this to render the graph visualization around any entity.
    """
    query = """
    MATCH (t {normalized_value: $val})-[r]-(neighbor)
    RETURN type(r) AS relationship, labels(neighbor) AS neighbor_labels,
           neighbor.normalized_value AS neighbor_value, r.source_doc AS source_document
    """
    with driver.session() as session:
        result = session.run(query, val=normalized_value)
        neighbors = [dict(r) for r in result]

    if not neighbors:
        raise HTTPException(status_code=404, detail=f"No entity found with normalized_value '{normalized_value}'")

    return {"entity": normalized_value, "neighbors": neighbors}


# ---------- Cross-document path (the core demo capability) ----------

@app.get("/entity/{from_entity}/path-to/{to_entity}", response_model=CrossDocPathResponse)
def get_cross_document_path(from_entity: str, to_entity: str, max_hops: int = 3):
    """
    Finds a path between two entities, showing which documents it crosses.
    e.g. GET /entity/TANK-01/path-to/SN-2053474
    """
    query = f"""
    MATCH path = (a {{normalized_value: $from_val}})-[*1..{max_hops}]-(b {{normalized_value: $to_val}})
    RETURN [n IN nodes(path) | n.normalized_value] AS path_nodes,
           [r IN relationships(path) | type(r)] AS path_relationships,
           [r IN relationships(path) | r.source_doc] AS source_documents_crossed
    LIMIT 5
    """
    with driver.session() as session:
        result = session.run(query, from_val=from_entity, to_val=to_entity)
        paths = [dict(r) for r in result]

    return {"found": len(paths) > 0, "paths": paths}


# ---------- Full graph snapshot (for frontend graph rendering) ----------

@app.get("/graph/snapshot")
def get_graph_snapshot(limit: int = 100):
    """Returns a bounded snapshot of the graph — nodes + edges — for
    rendering with a frontend graph library (e.g. react-force-graph, vis.js)."""
    query = """
    MATCH (n)-[r]-(m)
    RETURN DISTINCT n.normalized_value AS source, labels(n) AS source_labels,
           type(r) AS relationship, m.normalized_value AS target, labels(m) AS target_labels
    LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        edges = [dict(r) for r in result]

    nodes = {}
    for e in edges:
        nodes[e["source"]] = e["source_labels"]
        nodes[e["target"]] = e["target_labels"]

    return {
        "nodes": [{"id": k, "labels": v} for k, v in nodes.items()],
        "edges": [{"source": e["source"], "target": e["target"], "relationship": e["relationship"]} for e in edges],
    }


# ---------- Ask a question (routes through schema-conditioned retrieval) ----------

@app.post("/query", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    """
    Main Q&A endpoint. Routes the question through the schema-conditioned
    graph planner, falling back to vector/keyword search per router.py logic.
    """
    try:
        from router import route_query
        result = route_query(request.question)
        return {"question": request.question, "route": result.get("route", "unknown"), "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query routing failed: {e}")


# ---------- Demo fallback (pre-cached, guaranteed-working results) ----------

@app.get("/demo/fallback")
def get_demo_fallback():
    """Returns the pre-cached demo proof, in case live graph queries fail during judging."""
    try:
        with open("demo_fallback_cache.json") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Fallback cache not found — run build_fallback_cache.py first")


@app.on_event("shutdown")
def shutdown():
    driver.close()