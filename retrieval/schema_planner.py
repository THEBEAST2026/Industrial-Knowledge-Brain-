"""
Schema-conditioned planning stage.

This is the piece that distinguishes schema-constrained retrieval from a
plain "vector vs graph vs keyword" classifier: before ANY graph traversal
happens, an LLM call proposes a step-by-step plan (which entity types to
start from, which relationships to follow, in what order) — and that plan
is validated against graph_schema.py's VALID_PATHS in code, not trusted
blindly. Invalid plans are rejected and the agent is asked to replan or
fall back to vector/keyword search.

This directly prevents the failure mode named in the brief: an LLM
"reasoning" its way into asking for a nonexistent relationship (e.g.
Equipment -> SoftwareVersion) and either hallucinating an answer or
generating broken Cypher.
"""
import os
import json
import httpx
from graph_schema import schema_as_prompt_text, is_valid_hop, ENTITY_TYPES, RELATIONSHIP_TYPES

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "nousresearch/hermes-3-llama-3.1-405b"

PLANNING_PROMPT_TEMPLATE = """You are a retrieval planner for an industrial knowledge graph.
Your job is NOT to answer the question — only to propose a traversal plan
using the graph's actual schema. You must never invent entity types or
relationships that are not listed below.

{schema}

USER QUESTION: "{question}"

Propose a plan as JSON with this exact structure:
{{
  "start_entity_type": "<one of the entity types above>",
  "start_entity_hint": "<the specific value to start from, extracted from the question, e.g. 'TANK-01'>",
  "hops": [
    {{"relationship": "<relationship type>", "target_entity_type": "<entity type>"}}
  ],
  "reasoning": "<one sentence on why this plan answers the question>"
}}

Rules:
- Every hop MUST be a valid (start_or_previous_type, relationship, target_type)
  triple from the schema above. Do not propose hops that aren't listed.
- If the question cannot be answered via graph traversal (e.g. it's a general
  conceptual/safety question with no specific entity to anchor on), respond
  with exactly: {{"start_entity_type": null, "reasoning": "no valid graph anchor -> route to vector search"}}
- Keep the plan to at most 3 hops. Prefer the shortest valid path.

Respond with ONLY the JSON object, no markdown, no preamble."""


def propose_plan(question: str) -> dict:
    """Calls Hermes to propose a plan, given the schema as context."""
    prompt = PLANNING_PROMPT_TEMPLATE.format(schema=schema_as_prompt_text(), question=question)
    api_key = os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        return {"error": "no_api_key_set", "fallback": "route_to_vector_search"}

    try:
        resp = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0},
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        clean = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as e:
        return {"error": f"planning_call_failed: {e}", "fallback": "route_to_vector_search"}


def validate_plan(plan: dict) -> dict:
    """
    Code-level validation of the LLM's proposed plan against the schema —
    this is the actual enforcement step. The LLM prompt asks nicely; this
    function is what actually blocks an invalid plan from reaching Neo4j.
    """
    if not plan.get("start_entity_type"):
        return {"valid": False, "reason": plan.get("reasoning", "no graph anchor"), "plan": plan}

    if plan["start_entity_type"] not in ENTITY_TYPES:
        return {"valid": False, "reason": f"unknown start entity type: {plan['start_entity_type']}", "plan": plan}

    current_type = plan["start_entity_type"]
    for i, hop in enumerate(plan.get("hops", [])):
        rel = hop.get("relationship")
        target = hop.get("target_entity_type")

        if rel not in RELATIONSHIP_TYPES:
            return {"valid": False, "reason": f"hop {i}: unknown relationship '{rel}'", "plan": plan}
        if target not in ENTITY_TYPES:
            return {"valid": False, "reason": f"hop {i}: unknown target entity type '{target}'", "plan": plan}
        if not is_valid_hop(current_type, rel, target):
            return {"valid": False,
                     "reason": f"hop {i}: schema violation — no valid path {current_type} -[{rel}]-> {target}",
                     "plan": plan}
        current_type = target

    return {"valid": True, "plan": plan}


def plan_and_validate(question: str, max_replan_attempts: int = 1) -> dict:
    """
    Full planning pipeline: propose -> validate -> (replan once if invalid)
    -> return either a validated plan or a fallback instruction.
    """
    plan = propose_plan(question)
    validation = validate_plan(plan)

    attempts = 0
    while not validation["valid"] and attempts < max_replan_attempts and "error" not in plan:
        attempts += 1
        # In a full implementation, feed the rejection reason back into a
        # replanning prompt here. Kept simple for the demo: one retry with
        # the same call (temperature 0 means it may just repeat — a real
        # replan loop should append the rejection reason to the prompt).
        plan = propose_plan(question)
        validation = validate_plan(plan)

    if not validation["valid"]:
        return {"route": "vector_fallback", "reason": validation.get("reason", "planning failed"), "raw_plan": plan}

    return {"route": "graph_traversal", "plan": validation["plan"]}


if __name__ == "__main__":
    test_questions = [
        "What maintenance was performed on TANK-01, and how does it relate to the compressor inspection findings?",
        "What are the general safety precautions for LPG storage areas?",
        "What is the software version running on PUMP-04A?",  # should be rejected — no such path
    ]
    for q in test_questions:
        print(f"\nQUESTION: {q}")
        result = plan_and_validate(q)
        print(json.dumps(result, indent=2))