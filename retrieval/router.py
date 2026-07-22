
import re
from schema_executor import graph_search

EXACT_CODE_PATTERN = re.compile(r"^\s*[A-Z]{2,}-\d{2,5}[A-Z]?\s*$")


def keyword_search(query: str) -> dict:
    """Placeholder for exact-match lookup against Qdrant/pgvector metadata
    or a simple index — wire in your actual keyword/BM25 search here."""
    return {"route": "keyword_search", "query": query,
            "note": "wire in actual keyword index — this is a stub"}


def vector_search(query: str) -> dict:
    """Placeholder for Qdrant/pgvector semantic search — wire in your
    actual embedding + similarity search here."""
    return {"route": "vector_search", "query": query,
            "note": "wire in actual Qdrant/pgvector call — this is a stub"}


def route_query(question: str) -> dict:
    # Cheap short-circuit: if the whole query is just a code/tag, treat as
    # keyword lookup rather than paying for a planning LLM call.
    if EXACT_CODE_PATTERN.match(question):
        return keyword_search(question)

    # Try schema-conditioned graph planning first.
    graph_result = graph_search(question)

    if graph_result["route"] == "graph_traversal":
        if graph_result.get("results"):
            return graph_result
        # Valid schema-compliant plan, but zero results in the actual graph
        # (e.g. entity doesn't exist yet) -> fall back rather than return empty.
        return {
            **vector_search(question),
            "fallback_reason": "graph plan was valid but returned no results",
            "graph_plan_attempted": graph_result.get("plan"),
        }

    # Planner found no valid graph anchor -> conceptual/narrative question
    return {
        **vector_search(question),
        "fallback_reason": graph_result.get("reason", "no valid graph plan"),
    }


if __name__ == "__main__":
    test_questions = [
        "TANK-01",  # exact code -> keyword
        "What maintenance was performed on TANK-01, and who maintained it?",  # graph
        "What are general safety precautions for LPG storage?",  # vector fallback
    ]
    for q in test_questions:
        print(f"\nQUESTION: {q}")
        result = route_query(q)
        print(f"  Route taken: {result['route']}")
        if "fallback_reason" in result:
            print(f"  Fallback reason: {result['fallback_reason']}")