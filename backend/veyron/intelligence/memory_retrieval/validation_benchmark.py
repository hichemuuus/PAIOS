"""Validation benchmark — heuristic retrieval vs learned TF-IDF reranker.

Compares the existing MemoryStore keyword + quality-score search against the
trained MemoryRetrievalModel reranker on real Veyron synthetic interaction data.

Metrics:
  - MRR (Mean Reciprocal Rank)
  - Precision@K (K=1,3,5)
  - Recall@K (K=1,3,5)
  - Mean latency per query (heuristic vs reranker)

Usage:
    python -m veyron.intelligence.memory_retrieval.validation_benchmark
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("validation_benchmark")

DATA_FILE = Path(__file__).resolve().parents[3] / "data" / "training" / "synthetic_training_data.jsonl"
N_QUERIES = 200
CANDIDATES_PER_QUERY = 50
RELEVANT_PER_QUERY = 5
N_DISTRACTORS = CANDIDATES_PER_QUERY - RELEVANT_PER_QUERY
SEED = 42

K_VALUES = (1, 3, 5)


def load_synthetic_data(path: str | Path = DATA_FILE) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_memory_text(record: dict[str, Any]) -> str:
    intent = record.get("intent", "")
    tools = ", ".join(record.get("expected_tools", []))
    params = record.get("expected_parameters", {})
    params_str = "; ".join(f"{k}={v}" for k, v in params.items()) if params else ""
    parts = [record.get("request", "")]
    if intent:
        parts.append(f"intent: {intent}")
    if tools:
        parts.append(f"tools: {tools}")
    if params_str:
        parts.append(f"params: {params_str}")
    return ". ".join(parts)


def heuristic_score(query: str, memory_text: str, memory: dict[str, Any]) -> float:
    ql = query.lower()
    ml = memory_text.lower()
    if ql not in ml:
        return 0.0
    score = 0.5
    count = ml.count(ql)
    score += 0.05 * count
    difficulty_bonus = {"easy": 0.0, "moderate": 0.1, "hard": 0.2}
    score += difficulty_bonus.get(memory.get("difficulty", "easy"), 0.0)
    if memory.get("planning_required", False):
        score += 0.1
    return score


def heuristic_retrieve(
    query: str,
    candidates: list[dict[str, Any]],
    candidate_texts: list[str],
    top_k: int = 5,
) -> list[int]:
    scored: list[tuple[float, int]] = []
    for i, (rec, text) in enumerate(zip(candidates, candidate_texts)):
        s = heuristic_score(query, text, rec)
        if s > 0:
            scored.append((s, i))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [idx for _, idx in scored[:top_k]]


def main() -> None:
    logger.info("=" * 60)
    logger.info("MEMORY RETRIEVAL VALIDATION BENCHMARK")
    logger.info("=" * 60)

    records = load_synthetic_data()
    logger.info("Loaded %d synthetic records", len(records))

    rng = random.Random(SEED)

    intent_groups: dict[str, list[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        intent_groups[rec.get("intent", "unknown")].append(i)

    logger.info("Intent distribution: %s", {k: len(v) for k, v in sorted(intent_groups.items())})

    memory_texts = [build_memory_text(r) for r in records]
    sample_mem = memory_texts[0]
    logger.info("Sample memory text: %s", sample_mem[:100])

    queries: list[tuple[str, int, str]] = []
    for intent, indices in intent_groups.items():
        chosen = rng.sample(indices, min(N_QUERIES // len(intent_groups), len(indices)))
        for idx in chosen:
            queries.append((records[idx]["request"], idx, intent))

    rng.shuffle(queries)
    queries = queries[:N_QUERIES]
    logger.info("Selected %d query records for evaluation", len(queries))

    query_results: list[dict[str, Any]] = []

    for q_idx, (query, query_record_idx, query_intent) in enumerate(queries):
        same_intent_indices = [i for i in intent_groups[query_intent] if i != query_record_idx]
        if len(same_intent_indices) < RELEVANT_PER_QUERY:
            continue
        relevant = rng.sample(same_intent_indices, RELEVANT_PER_QUERY)

        other_indices = [i for i in range(len(records)) if i != query_record_idx and i not in relevant]
        distractors = rng.sample(
            other_indices, min(N_DISTRACTORS, len(other_indices))
        )

        candidate_indices = relevant + distractors
        rng.shuffle(candidate_indices)
        candidate_records = [records[i] for i in candidate_indices]
        candidate_texts = [memory_texts[i] for i in candidate_indices]
        relevant_set = set(range(len(relevant)))

        rel_map: dict[int, bool] = {}
        for pos, ci in enumerate(candidate_indices):
            rel_map[pos] = ci in relevant

        relevant_positions = [pos for pos, is_rel in rel_map.items() if is_rel]

        # --- Heuristic ---
        t0 = time.perf_counter()
        heur_results = heuristic_retrieve(query, candidate_records, candidate_texts, top_k=max(K_VALUES))
        heur_latency = (time.perf_counter() - t0) * 1000

        # --- Reranker ---
        t0 = time.perf_counter()
        try:
            from veyron.intelligence.memory_retrieval.inference import _load_model
            mr_model = _load_model()
            if mr_model is not None and mr_model.fitted:
                rerank_results = mr_model.predict(query, candidate_texts, top_k=max(K_VALUES))
            else:
                rerank_results = []
        except Exception:
            rerank_results = []
        rerank_latency = (time.perf_counter() - t0) * 1000

        query_results.append({
            "query": query,
            "query_intent": query_intent,
            "candidate_indices": candidate_indices,
            "relevant_positions": relevant_positions,
            "heuristic": heur_results,
            "reranker": rerank_results,
            "heuristic_latency_ms": heur_latency,
            "reranker_latency_ms": rerank_latency,
        })

    logger.info("Evaluated %d queries", len(query_results))

    # --- Aggregate metrics ---
    def precision_at_k(predicted: list[int], relevant: set[int], k: int) -> float:
        top = predicted[:k]
        if not top:
            return 0.0
        return sum(1 for idx in top if idx in relevant) / len(top)

    def recall_at_k(predicted: list[int], relevant: set[int], k: int) -> float:
        if not relevant:
            return 0.0
        top = predicted[:k]
        return sum(1 for idx in top if idx in relevant) / len(relevant)

    def mrr(predicted: list[int], relevant: set[int]) -> float:
        for rank, idx in enumerate(predicted, start=1):
            if idx in relevant:
                return 1.0 / rank
        return 0.0

    heur_metrics: dict[str, float] = {"mrr": 0.0}
    rerank_metrics: dict[str, float] = {"mrr": 0.0}
    for k in K_VALUES:
        heur_metrics[f"precision@{k}"] = 0.0
        heur_metrics[f"recall@{k}"] = 0.0
        rerank_metrics[f"precision@{k}"] = 0.0
        rerank_metrics[f"recall@{k}"] = 0.0

    n = len(query_results)
    heur_latencies: list[float] = []
    rerank_latencies: list[float] = []

    for qr in query_results:
        rel_set = set(qr["relevant_positions"])

        # Heuristic
        heur = qr["heuristic"]
        heur_metrics["mrr"] += mrr(heur, rel_set)
        for k in K_VALUES:
            heur_metrics[f"precision@{k}"] += precision_at_k(heur, rel_set, k)
            heur_metrics[f"recall@{k}"] += recall_at_k(heur, rel_set, k)
        heur_latencies.append(qr["heuristic_latency_ms"])

        # Reranker
        rer = qr["reranker"]
        rerank_metrics["mrr"] += mrr(rer, rel_set)
        for k in K_VALUES:
            rerank_metrics[f"precision@{k}"] += precision_at_k(rer, rel_set, k)
            rerank_metrics[f"recall@{k}"] += recall_at_k(rer, rel_set, k)
        rerank_latencies.append(qr["reranker_latency_ms"])

    for k in ["mrr"] + [f"precision@{k}" for k in K_VALUES] + [f"recall@{k}" for k in K_VALUES]:
        heur_metrics[k] = round(heur_metrics[k] / n, 4)
        rerank_metrics[k] = round(rerank_metrics[k] / n, 4)

    heur_avg_lat = round(sum(heur_latencies) / n, 3)
    rerank_avg_lat = round(sum(rerank_latencies) / n, 3)

    # --- Results ---
    logger.info("")
    logger.info("%-25s  %12s  %12s  %10s", "Metric", "Heuristic", "Reranker", "Delta")
    logger.info("-" * 62)

    def fmt(v: float) -> str:
        return f"{v:.4f}"

    def delta(h: float, r: float) -> str:
        d = r - h
        sign = "+" if d >= 0 else ""
        return f"{sign}{d:.4f}"

    for k in ["mrr"] + [f"precision@{k}" for k in K_VALUES]:
        h = heur_metrics[k]
        r = rerank_metrics[k]
        logger.info("%-25s  %12s  %12s  %10s", k, fmt(h), fmt(r), delta(h, r))

    for k in [f"recall@{k}" for k in K_VALUES]:
        h = heur_metrics[k]
        r = rerank_metrics[k]
        logger.info("%-25s  %12s  %12s  %10s", k, fmt(h), fmt(r), delta(h, r))

    logger.info("-" * 62)
    logger.info("%-25s  %12s  %12s  %10s", "latency_ms", f"{heur_avg_lat}", f"{rerank_avg_lat}", f"{rerank_avg_lat - heur_avg_lat:+.3f}")

    # --- Per-intent breakdown ---
    logger.info("")
    logger.info("PER-INTENT MRR BREAKDOWN")
    logger.info("-" * 40)
    intent_mrr: dict[str, dict[str, float]] = {}
    for qr in query_results:
        intent = qr["query_intent"]
        if intent not in intent_mrr:
            intent_mrr[intent] = {"count": 0, "heuristic_mrr": 0.0, "reranker_mrr": 0.0}
        rel_set = set(qr["relevant_positions"])
        intent_mrr[intent]["count"] += 1
        intent_mrr[intent]["heuristic_mrr"] += mrr(qr["heuristic"], rel_set)
        intent_mrr[intent]["reranker_mrr"] += mrr(qr["reranker"], rel_set)

    for intent in sorted(intent_mrr):
        v = intent_mrr[intent]
        cnt = v["count"]
        h_mrr = round(v["heuristic_mrr"] / cnt, 4)
        r_mrr = round(v["reranker_mrr"] / cnt, 4)
        d = r_mrr - h_mrr
        sign = "+" if d >= 0 else ""
        logger.info("%-22s  heur=%.4f  rerank=%.4f  (%s%.4f)", intent, h_mrr, r_mrr, sign, d)

    # --- Summary pass/fail ---
    mrr_improvement = rerank_metrics["mrr"] - heur_metrics["mrr"]
    avg_precision_improvement = sum(
        rerank_metrics[f"precision@{k}"] - heur_metrics[f"precision@{k}"] for k in K_VALUES
    ) / len(K_VALUES)
    avg_recall_improvement = sum(
        rerank_metrics[f"recall@{k}"] - heur_metrics[f"recall@{k}"] for k in K_VALUES
    ) / len(K_VALUES)

    logger.info("=" * 62)
    logger.info("SUMMARY")
    logger.info("  MRR improvement:          %+.4f" % mrr_improvement)
    logger.info("  Avg Precision@K improvement: %+.4f" % avg_precision_improvement)
    logger.info("  Avg Recall@K improvement:    %+.4f" % avg_recall_improvement)
    logger.info("  Reranker latency impact:   %+.3f ms" % (rerank_avg_lat - heur_avg_lat))

    if mrr_improvement > 0:
        logger.info("  -> Reranker WINS on MRR")
    elif mrr_improvement < 0:
        logger.info("  -> Heuristic WINS on MRR")
    else:
        logger.info("  -> TIE on MRR")

    if avg_precision_improvement > 0:
        logger.info("  -> Reranker WINS on Precision@K")
    elif avg_precision_improvement < 0:
        logger.info("  -> Heuristic WINS on Precision@K")
    else:
        logger.info("  -> TIE on Precision@K")

    if avg_recall_improvement > 0:
        logger.info("  -> Reranker WINS on Recall@K")
    elif avg_recall_improvement < 0:
        logger.info("  -> Heuristic WINS on Recall@K")
    else:
        logger.info("  -> TIE on Recall@K")


if __name__ == "__main__":
    main()
