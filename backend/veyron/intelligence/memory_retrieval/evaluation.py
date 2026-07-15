"""Evaluation for the memory retrieval micro-model.

Retrieval is a ranking task, so we measure rank-aware metrics:

  - **precision@k**: of the top-k predictions, what fraction are relevant?
  - **recall@k**:    of the relevant items, what fraction appear in the top-k?
  - **MRR**:         mean reciprocal rank — 1/rank of the first relevant hit.

These follow the conventions of ``tool_selector.metrics`` (the other rank-based
micro-model in the stack) while adding MRR, which is the standard headline
metric for retrieval.

``evaluate_model`` is the entrypoint the Phase 11.5 benchmark calls: it takes a
fitted model + a list of benchmark case dicts and returns an aggregate metrics
dict, mirroring ``ParameterExtractionEvaluator.evaluate_model``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from veyron.intelligence.memory_retrieval.model import MemoryRetrievalModel
from veyron.intelligence.memory_retrieval.schema import (
    DEFAULT_K_VALUES,
    MemoryRetrievalExample,
    MemoryRetrievalPrediction,
)


@dataclass
class MemoryRetrievalEvalResult:
    """Per-case evaluation result."""

    precision_at_k: dict[int, float] = field(default_factory=dict)
    recall_at_k: dict[int, float] = field(default_factory=dict)
    reciprocal_rank: float = 0.0
    relevant_found: int = 0
    relevant_total: int = 0


class MemoryRetrievalEvaluator:
    """Rank-aware evaluator for the memory retrieval model."""

    # ── Static rank metrics ──────────────────────────────────────────────────

    @staticmethod
    def precision_at_k(
        predicted: list[int], relevant: list[int], k: int
    ) -> float:
        """Precision@k: fraction of top-k predicted indices that are relevant."""
        if k <= 0:
            return 0.0
        top = predicted[:k]
        if not top:
            return 0.0
        rel_set = set(relevant)
        hits = sum(1 for idx in top if idx in rel_set)
        return hits / len(top)

    @staticmethod
    def recall_at_k(
        predicted: list[int], relevant: list[int], k: int
    ) -> float:
        """Recall@k: fraction of relevant items found in the top-k."""
        if not relevant:
            return 0.0
        top = predicted[:k]
        rel_set = set(relevant)
        found = sum(1 for idx in top if idx in rel_set)
        return found / len(rel_set)

    @staticmethod
    def reciprocal_rank(predicted: list[int], relevant: list[int]) -> float:
        """Reciprocal rank: 1/rank of the first relevant prediction (0 if none)."""
        rel_set = set(relevant)
        for rank, idx in enumerate(predicted, start=1):
            if idx in rel_set:
                return 1.0 / rank
        return 0.0

    # ── Per-case ────────────────────────────────────────────────────────────

    def evaluate_prediction(
        self,
        prediction: MemoryRetrievalPrediction,
        ground_truth: MemoryRetrievalExample,
    ) -> MemoryRetrievalEvalResult:
        """Evaluate a single prediction against its ground-truth example."""
        predicted = prediction.top_k or prediction.ranked_indices
        relevant = list(ground_truth.relevant_indices)
        result = MemoryRetrievalEvalResult(
            reciprocal_rank=self.reciprocal_rank(predicted, relevant),
            relevant_total=len(relevant),
        )
        rel_set = set(relevant)
        result.relevant_found = sum(1 for idx in predicted if idx in rel_set)
        for k in DEFAULT_K_VALUES:
            result.precision_at_k[k] = self.precision_at_k(predicted, relevant, k)
            result.recall_at_k[k] = self.recall_at_k(predicted, relevant, k)
        return result

    # ── Batch ───────────────────────────────────────────────────────────────

    def evaluate(
        self,
        predictions: list[MemoryRetrievalPrediction],
        ground_truths: list[MemoryRetrievalExample],
    ) -> dict[str, Any]:
        """Aggregate metrics across a batch of predictions.

        Raises ``ValueError`` on length mismatch, matching the parameter
        extraction evaluator's contract.
        """
        if len(predictions) != len(ground_truths):
            raise ValueError(
                f"predictions/ground_truths length mismatch: "
                f"{len(predictions)} != {len(ground_truths)}"
            )
        n = len(predictions)
        if n == 0:
            return {"total": 0}

        agg: dict[str, Any] = {"total": n}
        # Accumulators per k.
        p_sums = {k: 0.0 for k in DEFAULT_K_VALUES}
        r_sums = {k: 0.0 for k in DEFAULT_K_VALUES}
        rr_sum = 0.0
        per_category: dict[str, dict[str, float]] = {}

        for pred, gt in zip(predictions, ground_truths):
            res = self.evaluate_prediction(pred, gt)
            for k in DEFAULT_K_VALUES:
                p_sums[k] += res.precision_at_k[k]
                r_sums[k] += res.recall_at_k[k]
            rr_sum += res.reciprocal_rank

            cat = gt.category or "uncategorised"
            bucket = per_category.setdefault(
                cat, {"mrr_sum": 0.0, "count": 0}
            )
            bucket["mrr_sum"] += res.reciprocal_rank
            bucket["count"] += 1

        for k in DEFAULT_K_VALUES:
            agg[f"precision@{k}"] = round(p_sums[k] / n, 4)
            agg[f"recall@{k}"] = round(r_sums[k] / n, 4)
        agg["mrr"] = round(rr_sum / n, 4)

        agg["per_category"] = {
            cat: {"mrr": round(b["mrr_sum"] / b["count"], 4), "total": b["count"]}
            for cat, b in sorted(per_category.items())
        }
        return agg

    # ── Model-level (the benchmark contract) ────────────────────────────────

    def evaluate_model(
        self,
        model: MemoryRetrievalModel,
        test_cases: list[dict[str, Any]],
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Evaluate a fitted model on a list of benchmark case dicts.

        Each case dict has the shape::

            {
              "id": "...",
              "query": "...",
              "candidate_memories": ["...", "..."],
              "relevant_indices": [0, 2],
              "difficulty": "moderate",
              "category": "PROJECT"
            }

        Returns the aggregate metrics dict from :meth:`evaluate`, augmented with
        ``available: True``. If the model is None or not fitted, returns
        ``{"available": False, ...}`` so the benchmark can skip cleanly.
        """
        if model is None or not getattr(model, "fitted", False):
            return {"available": False, "total": len(test_cases), "note": "model not available"}

        predictions: list[MemoryRetrievalPrediction] = []
        ground_truths: list[MemoryRetrievalExample] = []
        for tc in test_cases:
            query = tc.get("query", "")
            candidates = tc.get("candidate_memories", [])
            relevant = tc.get("relevant_indices", [])
            ranked = model.predict(query, candidates, top_k=top_k)
            predictions.append(
                MemoryRetrievalPrediction(
                    query=query, top_k=ranked, ranked_indices=ranked
                )
            )
            ground_truths.append(
                MemoryRetrievalExample(
                    query=query,
                    candidate_memories=candidates,
                    relevant_indices=relevant,
                    difficulty=tc.get("difficulty", "basic"),
                    category=tc.get("category", ""),
                )
            )

        result = self.evaluate(predictions, ground_truths)
        result["available"] = True
        return result
