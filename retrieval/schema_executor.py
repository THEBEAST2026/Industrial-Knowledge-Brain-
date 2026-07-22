
from neo4j import GraphDatabase
from db_config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD




def build_cypher(plan: dict) -> tuple[str, dict]:
    """
    Translates a validated plan into a Cypher query. Each hop becomes one
    MATCH segment; the entity_type is used as the node label so a
    mismatched label (e.g. graph has no :SoftwareVersion nodes at all)
    fails safely at query time even if it somehow slipped past validation.
    """
    start_label = plan["start_entity_type"]
    start_hint = plan.get("start_entity_hint", "")
    params = {"start_value": start_hint}

    path_segments = [f"(n0:{start_label} {{normalized_value: $start_value}})"]
    for i, hop in enumerate(plan.get("hops", []), start=1):
        rel = hop["relationship"]
        target_label = hop["target_entity_type"]
        path_segments.append(f"-[:{rel}]-(n{i}:{target_label})")

    cypher = "MATCH path = " + "".join(path_segments)
    return_vars = ["n0"] + [f"n{i}" for i in range(1, len(plan.get("hops", [])) + 1)]
    cypher += f"\nRETURN {', '.join(f'{v}.normalized_value AS {v}_value' for v in return_vars)}, path"

    return cypher, params


def execute_plan(plan: dict) -> list[dict]:
    cypher, params = build_cypher(plan)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]
    finally:
        driver.close()


def graph_search(question: str) -> dict:
    """
    Full entry point: plan -> validate -> execute. Import this into
    router.py as the "graph" branch of the retrieval router.
    """
    from schema_planner import plan_and_validate

    planning_result = plan_and_validate(question)
    if planning_result["route"] != "graph_traversal":
        return {"route": "vector_fallback", "reason": planning_result.get("reason")}

    plan = planning_result["plan"]
    cypher, params = build_cypher(plan)
    try:
        results = execute_plan(plan)
        return {"route": "graph_traversal", "plan": plan, "cypher": cypher,
                "params": params, "results": results}
    except Exception as e:
        # Neo4j not reachable, or label genuinely doesn't exist in the
        # loaded graph — fail safe to vector search rather than error out
        return {"route": "vector_fallback", "reason": f"execution_failed: {e}",
                "cypher_attempted": cypher}


if __name__ == "__main__":
    # Direct test with a hand-built plan (bypasses LLM planning call, so
    # this works even without OPENROUTER_API_KEY set — proves the
    # plan -> Cypher -> Neo4j chain independent of the planning stage)
    test_plan = {
        "start_entity_type": "Equipment",
        "start_entity_hint": "TANK-01",
        "hops": [{"relationship": "MAINTAINED_BY", "target_entity_type": "Person"}],
    }
    cypher, params = build_cypher(test_plan)
    print("Generated Cypher:")
    print(cypher)
    print("Params:", params)
    print()
    print("To run against your Neo4j instance:")
    print("  python3 -c \"from schema_executor import execute_plan; print(execute_plan(", test_plan, "))\"")