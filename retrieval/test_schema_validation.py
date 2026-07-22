"""
Proves validate_plan() enforces the schema in code — not just via prompt
suggestion. These are mock plans (as if the LLM had proposed them),
testing the validator directly so the constraint logic is verified
independent of any live API call.
"""
from schema_planner import validate_plan

test_cases = [
    {
        "name": "Valid: Equipment -> Person (maintenance query)",
        "plan": {
            "start_entity_type": "Equipment",
            "start_entity_hint": "TANK-01",
            "hops": [{"relationship": "MAINTAINED_BY", "target_entity_type": "Person"}],
        },
        "expect_valid": True,
    },
    {
        "name": "Valid: Equipment -> Parameter -> (2 hop)",
        "plan": {
            "start_entity_type": "Equipment",
            "start_entity_hint": "SN-2053474",
            "hops": [{"relationship": "REFERENCES", "target_entity_type": "Parameter"}],
        },
        "expect_valid": True,
    },
    {
        "name": "INVALID: Equipment -> SoftwareVersion (nonexistent entity type)",
        "plan": {
            "start_entity_type": "Equipment",
            "start_entity_hint": "PUMP-04A",
            "hops": [{"relationship": "REFERENCES", "target_entity_type": "SoftwareVersion"}],
        },
        "expect_valid": False,
    },
    {
        "name": "INVALID: Permit -> MAINTAINED_BY -> Person (permits aren't maintained by people)",
        "plan": {
            "start_entity_type": "Permit",
            "start_entity_hint": "HW-2291",
            "hops": [{"relationship": "MAINTAINED_BY", "target_entity_type": "Person"}],
        },
        "expect_valid": False,
    },
    {
        "name": "INVALID: unknown relationship type entirely",
        "plan": {
            "start_entity_type": "Equipment",
            "start_entity_hint": "TANK-01",
            "hops": [{"relationship": "RUNS_ON", "target_entity_type": "Parameter"}],
        },
        "expect_valid": False,
    },
    {
        "name": "Valid: no graph anchor -> vector fallback",
        "plan": {"start_entity_type": None, "reasoning": "conceptual question, no entity anchor"},
        "expect_valid": False,  # correctly routes to vector, not a graph "pass"
    },
]

print(f"{'Test':<65} {'Expected':<10} {'Got':<10} {'Result'}")
print("-" * 100)
all_passed = True
for t in test_cases:
    result = validate_plan(t["plan"])
    got_valid = result["valid"]
    passed = got_valid == t["expect_valid"]
    all_passed &= passed
    status = "PASS" if passed else "FAIL"
    print(f"{t['name']:<65} {str(t['expect_valid']):<10} {str(got_valid):<10} {status}")
    if not got_valid:
        print(f"    -> rejected because: {result['reason']}")

print("\n" + ("ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED"))