
import json
import re
import itertools
from collections import defaultdict
from rapidfuzz import fuzz
import networkx as nx

FUZZY_AUTO_MERGE_THRESHOLD = 92   # above this: merge automatically, high confidence
FUZZY_REVIEW_THRESHOLD = 70       # between review and auto: send to LLM validation
                                   # below review threshold: treat as distinct entities


# ---------- Stage 1: Deterministic blocking ----------

def blocking_key(entity_type: str, normalized_value: str) -> str:
    """
    Coarse key to avoid comparing every entity to every other entity
    (O(n^2) is fine at 1,600 entities, but blocking is what makes this
    approach scale to a real plant's document corpus later).
    Strategy: entity_type + alphabetic prefix (strips trailing digits so
    "PUMP-04A" and "PUMP-04B" land in the same block as "P-04A").
    """
    alpha_prefix = re.match(r"^[A-Z]+", normalized_value.replace("-", ""))
    prefix = alpha_prefix.group(0)[:4] if alpha_prefix else normalized_value[:4]
    return f"{entity_type}::{prefix}"


def build_blocks(all_entities: list[dict]) -> dict:
    blocks = defaultdict(list)
    for e in all_entities:
        key = blocking_key(e["entity_type"], e["normalized_value"])
        blocks[key].append(e)
    return blocks


# ---------- Stage 2: Fuzzy matching within blocks ----------

def fuzzy_candidate_pairs(blocks: dict) -> list[tuple]:
    """Returns (entity_a, entity_b, score) for every same-block pair scoring
    above the review threshold — pairs below that are left as distinct.

    Two safeguards vs. naive string similarity:
    1. Dedupe to unique normalized_values before pairing — otherwise the
       same pair gets compared once per repeated mention (e.g. PUMP-04A
       appears in 40 worklog rows -> O(n^2) blowup on duplicates alone).
    2. Trailing-identifier guard: "PUMP-01" and "PUMP-03" are high string
       similarity but near-certainly DIFFERENT physical assets — the only
       thing that differs is the identifying suffix, which is precisely
       the part meant to distinguish them. Never auto-merge these; route
       to LLM review at most, same as the source material's guidance to
       fail toward DIFFERENT when uncertain.
    3. Type restriction: ER only makes sense for entity types where the
       SAME real-world thing can legitimately be named differently across
       documents (Equipment, Person). Permit numbers, dates, and parameter
       readings are inherently unique per record — "HW-2201" and "HW-2203"
       are two different permits, not two names for one permit. Comparing
       them for similarity produces noise, not useful candidates.
    """
    RESOLVABLE_TYPES = {"Equipment", "Person"}
    candidates = []
    for key, members in blocks.items():
        entity_type = key.split("::")[0]
        if entity_type not in RESOLVABLE_TYPES:
            continue

        # Deduplicate by normalized_value — keep one representative entity
        # dict per unique value (lineage is reattached later from the full list)
        unique_by_value = {}
        for m in members:
            unique_by_value.setdefault(m["normalized_value"], m)
        unique_members = list(unique_by_value.values())

        if len(unique_members) < 2:
            continue
        for a, b in itertools.combinations(unique_members, 2):
            score = fuzz.ratio(a["normalized_value"], b["normalized_value"])
            if score < FUZZY_REVIEW_THRESHOLD:
                continue

            # Trailing-identifier guard
            suffix_a = re.search(r"(\d+[A-Z]?)$", a["normalized_value"])
            suffix_b = re.search(r"(\d+[A-Z]?)$", b["normalized_value"])
            if suffix_a and suffix_b and suffix_a.group(1) != suffix_b.group(1):
                # Different trailing identifiers (e.g. -01 vs -03, -04A vs -04B)
                # -> cap score below auto-merge threshold regardless of overall
                # string similarity, forcing it to review or reject.
                score = min(score, FUZZY_AUTO_MERGE_THRESHOLD - 1)

            candidates.append((a, b, score))
    return candidates


# ---------- Stage 3: Weakly Connected Components clustering ----------

def cluster_with_wcc(all_entities: list[dict], auto_merge_pairs: list[tuple]) -> list[set]:
    """
    Builds a graph where nodes are normalized_values and edges are
    high-confidence fuzzy matches, then finds weakly connected components.
    Each component is a cluster of strings that should resolve to ONE
    canonical entity node.

    This is exactly what Neo4j GDS's WCC algorithm does, run here via
    networkx so it works without the GDS plugin installed. To run the
    equivalent directly in Neo4j once your graph is loaded:

        CALL gds.graph.project('entityGraph', '*', '*')
        CALL gds.wcc.stream('entityGraph')
        YIELD nodeId, componentId
        RETURN gds.util.asNode(nodeId).normalized_value AS entity, componentId
        ORDER BY componentId
    """
    G = nx.Graph()
    for e in all_entities:
        G.add_node(e["normalized_value"])
    for a, b, score in auto_merge_pairs:
        G.add_edge(a["normalized_value"], b["normalized_value"], weight=score)

    components = list(nx.connected_components(G))
    # Only keep components with more than 1 member — singletons aren't merges
    return [c for c in components if len(c) > 1]


# ---------- Stage 4: LLM-in-the-loop validation for uncertain matches ----------

def llm_validate_pair(entity_a: dict, entity_b: dict, score: float) -> dict:
    """
    For medium-confidence pairs (70-92), ask Hermes (via OpenRouter) to
    confirm whether two entity mentions are the SAME physical asset or
    DIFFERENT ones, using source context as evidence rather than trusting
    string similarity alone.

    Requires OPENROUTER_API_KEY set as an environment variable. Falls back
    to a safe "DIFFERENT" decision (never merge) if the API call fails,
    since a missed merge is far cheaper than a wrongly merged asset.
    """
    import os
    import httpx

    prompt = f"""Two entity mentions were found in industrial documents with
{score:.0f}% string similarity. Determine if they refer to the SAME physical
asset or DIFFERENT assets, using the source context as evidence.

Entity A: "{entity_a['value']}" (normalized: {entity_a['normalized_value']})
  Source document: {entity_a.get('chunk_id', 'unknown')}
  Type: {entity_a['entity_type']}

Entity B: "{entity_b['value']}" (normalized: {entity_b['normalized_value']})
  Source document: {entity_b.get('chunk_id', 'unknown')}
  Type: {entity_b['entity_type']}

Answer with only one word: SAME or DIFFERENT.
If uncertain, answer DIFFERENT (fail-safe — false negatives are cheaper
than incorrectly merging two different pieces of equipment)."""

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"decision": "DIFFERENT", "reason": "no_api_key_set", "prompt_used": prompt}

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "nousresearch/hermes-3-llama-3.1-405b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
            },
            timeout=20,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip().upper()
        decision = "SAME" if "SAME" in answer else "DIFFERENT"
        return {"decision": decision, "raw_response": answer, "prompt_used": prompt}
    except Exception as e:
        # Fail-safe: any API error -> treat as DIFFERENT, never merge blind
        return {"decision": "DIFFERENT", "reason": f"api_error: {e}", "prompt_used": prompt}


# ---------- Stage 5: Lineage-preserving merge ----------

def build_resolved_entities(all_entities: list[dict], clusters: list[set]) -> dict:
    """
    Produces the final resolved entity list. Merged clusters get ONE
    canonical node with a full source_lineage array — the original
    per-document mentions are preserved as audit trail, never deleted.
    """
    value_to_cluster = {}
    for cluster in clusters:
        canonical = sorted(cluster, key=len)[0]  # shortest form as canonical, e.g. "P-04A" over "PUMP-04A-UNIT2"
        for v in cluster:
            value_to_cluster[v] = canonical

    resolved = {}
    for e in all_entities:
        val = e["normalized_value"]
        canonical = value_to_cluster.get(val, val)
        if canonical not in resolved:
            resolved[canonical] = {
                "canonical_value": canonical,
                "entity_type": e["entity_type"],
                "merged_from": set(),
                "source_lineage": [],
                "first_seen_chunk": e.get("chunk_id"),
            }
        resolved[canonical]["merged_from"].add(val)
        resolved[canonical]["source_lineage"].append({
            "raw_value": e.get("value"),
            "normalized_value": val,
            "chunk_id": e.get("chunk_id"),
            "source_doc": e.get("source_doc", "unknown"),
        })

    # sets aren't JSON-serializable — convert before returning
    for v in resolved.values():
        v["merged_from"] = sorted(v["merged_from"])
    return resolved


def load_all_entities() -> list[dict]:
    all_entities = []

    worklog = json.load(open("sample_docs/extracted/worklog_entities.json"))
    for r in worklog:
        for e in r.get("entities", []):
            e["source_doc"] = r.get("source_doc")
            all_entities.append(e)

    pid = json.load(open("sample_docs/extracted/pid_entities.json"))
    for chunk in pid.get("chunks", []):
        for e in chunk.get("entities", []):
            e["source_doc"] = pid.get("source_doc")
            all_entities.append(e)

    inspection = json.load(open("sample_docs/extracted/inspection_entities.json"))
    for r in inspection:
        for e in r.get("entities", []):
            e["source_doc"] = r.get("source_doc")
            all_entities.append(e)

    return all_entities


if __name__ == "__main__":
    print("Loading entities from all extracted sources...")
    all_entities = load_all_entities()
    print(f"  {len(all_entities)} total entity mentions loaded")

    print("\nStage 1: Deterministic blocking...")
    blocks = build_blocks(all_entities)
    multi_member_blocks = {k: v for k, v in blocks.items() if len(v) > 1}
    print(f"  {len(blocks)} blocks created, {len(multi_member_blocks)} have 2+ candidates")

    print("\nStage 2: Fuzzy matching within blocks...")
    candidate_pairs = fuzzy_candidate_pairs(blocks)
    auto_merge = [(a, b, s) for a, b, s in candidate_pairs if s >= FUZZY_AUTO_MERGE_THRESHOLD]
    needs_review = [(a, b, s) for a, b, s in candidate_pairs if FUZZY_REVIEW_THRESHOLD <= s < FUZZY_AUTO_MERGE_THRESHOLD]
    print(f"  {len(candidate_pairs)} candidate pairs found")
    print(f"  {len(auto_merge)} auto-merge (>= {FUZZY_AUTO_MERGE_THRESHOLD}% similarity)")
    print(f"  {len(needs_review)} need LLM review ({FUZZY_REVIEW_THRESHOLD}-{FUZZY_AUTO_MERGE_THRESHOLD}%)")

    if auto_merge:
        print("\n  Auto-merge examples:")
        for a, b, s in auto_merge[:5]:
            print(f"    '{a['normalized_value']}' <-> '{b['normalized_value']}'  ({s:.0f}%)")

    print("\nStage 3: Weakly Connected Components clustering (auto-merge only, preview)...")
    preview_clusters = cluster_with_wcc(all_entities, auto_merge)
    print(f"  {len(preview_clusters)} merge clusters from high-confidence auto-merges alone")
    for c in preview_clusters[:5]:
        print(f"    Cluster: {sorted(c)}")

    print(f"\nStage 4: LLM-in-the-loop validation ({len(needs_review)} uncertain pairs)...")
    import os
    has_api_key = bool(os.environ.get("OPENROUTER_API_KEY"))
    if not has_api_key:
        print("  WARNING: OPENROUTER_API_KEY not set — all pairs will default to DIFFERENT (safe fallback).")
        print("  Set the env var and re-run to get real LLM validation decisions.")

    llm_confirmed_same = []
    for a, b, s in needs_review:
        result = llm_validate_pair(a, b, s)
        print(f"    '{a['normalized_value']}' vs '{b['normalized_value']}' ({s:.0f}%) -> {result['decision']}")
        if result["decision"] == "SAME":
            llm_confirmed_same.append((a, b, s))

    print(f"\n  {len(llm_confirmed_same)} pairs confirmed SAME by LLM, added to merge graph")

    print("\nStage 5: Building lineage-preserving resolved entity set...")
    # Final merge graph = high-confidence auto-merges + LLM-confirmed pairs
    all_merge_pairs = auto_merge + llm_confirmed_same
    clusters = cluster_with_wcc(all_entities, all_merge_pairs)
    print(f"  {len(clusters)} final merge clusters (after LLM validation)")

    resolved = build_resolved_entities(all_entities, clusters)
    print(f"  {len(all_entities)} raw mentions -> {len(resolved)} resolved canonical entities")

    merged_examples = {k: v for k, v in resolved.items() if len(v["merged_from"]) > 1}
    print(f"  {len(merged_examples)} entities have multiple source mentions merged")
    for k, v in list(merged_examples.items())[:3]:
        print(f"\n    Canonical: {k}")
        print(f"    Merged from: {v['merged_from']}")
        print(f"    Source lineage ({len(v['source_lineage'])} mentions):")
        for lin in v["source_lineage"]:
            print(f"      - {lin['raw_value']} (doc: {lin['source_doc']})")

    with open("sample_docs/extracted/resolved_entities.json", "w") as f:
        json.dump(resolved, f, indent=2)
    print("\nSaved -> sample_docs/extracted/resolved_entities.json")