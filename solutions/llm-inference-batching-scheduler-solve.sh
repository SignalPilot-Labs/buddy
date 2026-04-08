#!/bin/bash
set -e

# LLM Inference Batching Scheduler Solution
#
# Strategy:
# - Use 8 shapes shared across both plans to stay within the global shape cap.
# - Bucket 1 (B1): group requests by aligned_seq, then use a fixed gen_len spread
#   window (spread=8) to pack requests with similar gen_len into the same batch.
#   This minimises decode padding while reducing sequential_timecost from merging
#   adjacent gen_len groups.
# - Bucket 2 (B2): use a greedy priority-queue merge that maximises
#   sequential_timecost savings per decode_pad token, subject to:
#   (a) total decode_pad <= budget derived from pad_ratio limit,
#   (b) the resulting batch G_max does not push any request above the p95 threshold.

python3 - << 'PYEOF'
import json
import heapq
from collections import defaultdict, Counter

GRAN = 64
HEADS = 32
HIDDEN = 4096

# Latency constants (match cost_model.py CostConsts defaults)
TP_ATN = 0.002
TP_MLP = 0.0015
TD_ATN = 0.0012
TD_MLP = 0.0006
TBATCH_OVERHEAD_MS = 8.0

INPUT_DIR = "/app/task_file/input_data"
OUTPUT_DIR = "/app/task_file/output_data"

# 8 shapes shared across both plans.
# These cover all aligned_seq values present in B1 and B2:
#   B1 aligned seqs: 64,128,320,384,448,512,576,640,1088..2048
#   B2 aligned seqs: 64,128,192,256,320,384,448,512,576,640,704
# Assignment: seq -> min(shape >= seq) from SHAPES
SHAPES = [128, 256, 320, 448, 576, 704, 1280, 2048]

# Optimisation parameters
B1_GEN_SPREAD = 8         # Max gen_len spread within a B1 batch
B1_PAD_RATIO_LIMIT = 0.055
B2_PAD_RATIO_LIMIT = 0.15
B2_LAT_THRESHOLD = 2.1e5  # ms; merges that push G_max lat above this are skipped

import os
os.makedirs(OUTPUT_DIR, exist_ok=True)


def align(x: int, g: int) -> int:
    return ((x + g - 1) // g) * g


def sum_sq_arith(a: int, n: int) -> int:
    """Closed-form sum of (a+t)^2 for t in 0..n-1."""
    return n * (a * a) + a * n * (n - 1) + (n * (n - 1) * (2 * n - 1)) // 6


def single_request_latency(prompt_len: int, gen_len: int) -> float:
    """Latency for a single request with its own gen_len as G_max (no batch overhead)."""
    s = align(prompt_len, GRAN)
    prefill = TP_ATN * s * s + TP_MLP * s * HIDDEN
    ss = sum_sq_arith(s, gen_len)
    sl = gen_len * s + gen_len * (gen_len - 1) / 2
    decode = TD_ATN * ss + TD_MLP * sl
    return prefill + decode


def load_requests(path: str) -> list:
    with open(path) as f:
        return [json.loads(line) for line in f]


def assign_shape(seq: int, shapes: list) -> int:
    """Return the smallest shape >= seq, or the largest if none fits."""
    for sh in sorted(shapes):
        if sh >= seq:
            return sh
    return max(shapes)


def write_plan(path: str, plan: list) -> None:
    with open(path, "w") as f:
        for entry in plan:
            f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# B1 strategy: fixed gen_len spread window
# ---------------------------------------------------------------------------

def build_plan_b1(reqs: list, shapes: list, max_gen_spread: int) -> list:
    """
    For each aligned_seq group, sort requests by gen_len then pack into
    batches where max(gen_len) - min(gen_len) <= max_gen_spread.
    This bounds decode padding while keeping sequential_timecost manageable.
    """
    by_seq: dict = defaultdict(list)
    for r in reqs:
        s = align(r["prompt_len"], GRAN)
        by_seq[s].append(r)

    plan: list = []
    bid = 0

    for seq in sorted(by_seq.keys()):
        group = sorted(by_seq[seq], key=lambda r: r["gen_len"])
        shape_seq = assign_shape(seq, shapes)
        i = 0
        while i < len(group):
            batch = [group[i]]
            g_min = group[i]["gen_len"]
            i += 1
            while (i < len(group)
                   and group[i]["gen_len"] - g_min <= max_gen_spread):
                batch.append(group[i])
                i += 1
            bid += 1
            batch_id = f"b-{bid:04d}"
            for r in batch:
                plan.append({
                    "request_id": r["request_id"],
                    "batch_id": batch_id,
                    "shape": {
                        "seq_align": shape_seq,
                        "heads_align": HEADS,
                        "hidden_align": HIDDEN,
                    },
                })
    return plan


# ---------------------------------------------------------------------------
# B2 strategy: greedy priority-queue merge
# ---------------------------------------------------------------------------

def build_plan_b2(reqs: list, shapes: list, decode_pad_budget: int,
                  lat_threshold: float) -> list:
    """
    Greedy merge of adjacent gen_len groups within each aligned_seq bucket.
    Priority = sequential_timecost savings (ms) per decode_pad token consumed.
    Skips merges where the new G_max would produce latency > lat_threshold.
    """
    by_seq: dict = defaultdict(list)
    for r in reqs:
        s = align(r["prompt_len"], GRAN)
        by_seq[s].append(r)

    # Initial groups: each unique (aligned_seq, gen_len) is its own batch.
    # group entry: (frozenset_of_gen_lens, request_count, current_g_max)
    group_state: dict = {}
    for seq, seq_reqs in by_seq.items():
        gen_cnt = Counter(r["gen_len"] for r in seq_reqs)
        group_state[seq] = [
            (frozenset([g]), cnt, g)
            for g, cnt in sorted(gen_cnt.items())
        ]

    heap: list = []

    def compute_opportunity(seq: int, idx: int):
        """Return (efficiency, cost_tokens, save_ms, idx) or None."""
        groups = group_state[seq]
        if idx >= len(groups) - 1:
            return None
        g_lower = groups[idx]
        g_upper = groups[idx + 1]
        # Reject if the upper group's G_max would violate p95 latency guard.
        if single_request_latency(seq, g_upper[2]) > lat_threshold:
            return None
        # Extra decode_pad tokens consumed by merging g_lower into g_upper.
        cost_tokens = (g_upper[2] - g_lower[2]) * g_lower[1]
        if cost_tokens <= 0:
            return None
        # Sequential_timecost saving: we eliminate g_lower's batch entirely.
        save_ms = single_request_latency(seq, g_lower[2]) + TBATCH_OVERHEAD_MS
        efficiency = save_ms / cost_tokens
        return (efficiency, cost_tokens, save_ms, idx)

    # Seed the heap.
    for seq in group_state:
        for i in range(len(group_state[seq]) - 1):
            opp = compute_opportunity(seq, i)
            if opp is not None:
                eff, cost, save, idx = opp
                heapq.heappush(heap, (-eff, seq, idx, len(group_state[seq])))

    budget = decode_pad_budget

    while heap and budget > 0:
        neg_eff, seq, idx, version = heapq.heappop(heap)
        groups = group_state[seq]

        # Stale entry: group structure changed since this was pushed.
        if version != len(groups):
            if idx < len(groups) - 1:
                opp = compute_opportunity(seq, idx)
                if opp is not None:
                    eff, cost, save, _ = opp
                    heapq.heappush(heap, (-eff, seq, idx, len(groups)))
            continue

        if idx >= len(groups) - 1:
            continue

        opp = compute_opportunity(seq, idx)
        if opp is None:
            continue

        eff, cost_tokens, save_ms, _ = opp
        if cost_tokens > budget:
            continue

        # Merge group[idx] (lower) into group[idx+1] (upper).
        g_lower = groups[idx]
        g_upper = groups[idx + 1]
        groups[idx] = (
            g_lower[0] | g_upper[0],
            g_lower[1] + g_upper[1],
            g_upper[2],
        )
        groups.pop(idx + 1)
        budget -= cost_tokens

        # Re-evaluate the opportunity between new groups[idx] and groups[idx+1].
        if idx < len(groups) - 1:
            opp_next = compute_opportunity(seq, idx)
            if opp_next is not None:
                eff_n, cost_n, save_n, _ = opp_next
                heapq.heappush(heap, (-eff_n, seq, idx, len(groups)))

        # Re-evaluate between groups[idx-1] and groups[idx] since
        # groups[idx].g_max changed (cost of that merge changed too).
        if idx > 0:
            opp_prev = compute_opportunity(seq, idx - 1)
            if opp_prev is not None:
                eff_p, cost_p, save_p, _ = opp_prev
                heapq.heappush(heap, (-eff_p, seq, idx - 1, len(groups)))

    # Build plan from final group state.
    plan: list = []
    bid = 0

    for seq in sorted(group_state.keys()):
        groups = group_state[seq]
        by_gen: dict = defaultdict(list)
        for r in by_seq[seq]:
            by_gen[r["gen_len"]].append(r)

        shape_seq = assign_shape(seq, shapes)

        for group_gens, group_count, g_max in groups:
            bid += 1
            batch_id = f"b-{bid:04d}"
            batch_reqs = [
                r for g in sorted(group_gens) for r in by_gen[g]
            ]
            for r in batch_reqs:
                plan.append({
                    "request_id": r["request_id"],
                    "batch_id": batch_id,
                    "shape": {
                        "seq_align": shape_seq,
                        "heads_align": HEADS,
                        "hidden_align": HIDDEN,
                    },
                })
    return plan


def decode_pad_budget(reqs: list, pad_ratio_limit: float) -> int:
    """Remaining decode_pad tokens after fixed prefill alignment padding."""
    real_tokens = sum(r["prompt_len"] + r["gen_len"] for r in reqs)
    prefill_pad = sum(
        align(r["prompt_len"], GRAN) - r["prompt_len"] for r in reqs
    )
    max_total_pad = int(pad_ratio_limit * real_tokens)
    return max(0, max_total_pad - prefill_pad)


# Load inputs
reqs1 = load_requests(f"{INPUT_DIR}/requests_bucket_1.jsonl")
reqs2 = load_requests(f"{INPUT_DIR}/requests_bucket_2.jsonl")

# Build plans
plan_b1 = build_plan_b1(reqs1, SHAPES, B1_GEN_SPREAD)
plan_b2 = build_plan_b2(
    reqs2, SHAPES,
    decode_pad_budget(reqs2, B2_PAD_RATIO_LIMIT),
    B2_LAT_THRESHOLD,
)

# Write outputs
write_plan(f"{OUTPUT_DIR}/plan_b1.jsonl", plan_b1)
write_plan(f"{OUTPUT_DIR}/plan_b2.jsonl", plan_b2)

n_batches_b1 = len(set(p["batch_id"] for p in plan_b1))
n_batches_b2 = len(set(p["batch_id"] for p in plan_b2))
sh1 = set(
    (p["shape"]["seq_align"], p["shape"]["heads_align"], p["shape"]["hidden_align"])
    for p in plan_b1
)
sh2 = set(
    (p["shape"]["seq_align"], p["shape"]["heads_align"], p["shape"]["hidden_align"])
    for p in plan_b2
)
combined_shapes = sh1 | sh2

print(f"B1: {len(plan_b1)} requests in {n_batches_b1} batches")
print(f"B2: {len(plan_b2)} requests in {n_batches_b2} batches")
print(f"Combined unique shapes: {len(combined_shapes)} (limit 8)")
print(f"Shape seq_aligns used: {sorted(s[0] for s in combined_shapes)}")
print("Done.")
PYEOF
