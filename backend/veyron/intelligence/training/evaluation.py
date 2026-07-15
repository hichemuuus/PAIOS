"""Comprehensive evaluation metrics and reports for trained micro-models.

Provides:
  - IntentEvaluator: full intent classification evaluation
  - ToolSelectorEvaluator: full tool selection evaluation
  - ModelComparison: compare two model versions
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from veyron.intelligence.intent.model import IntentModel
from veyron.intelligence.tool_selector.metrics import ToolSelectionMetrics
from veyron.intelligence.tool_selector.model import ToolSelectorModel

logger = logging.getLogger(__name__)


@dataclass
class IntentEvalReport:
    accuracy: float = 0.0
    correct: int = 0
    total: int = 0
    macro_precision: float = 0.0
    macro_recall: float = 0.0
    macro_f1: float = 0.0
    per_category: dict[str, dict[str, float]] = field(default_factory=dict)
    calibration: list[dict] = field(default_factory=list)
    confusion_matrix: dict[str, dict[str, int]] = field(default_factory=dict)
    common_mistakes: list[dict] = field(default_factory=list)
    mistake_examples: list[dict] = field(default_factory=list)
    weak_categories: list[str] = field(default_factory=list)
    avg_confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "accuracy": self.accuracy,
            "correct": self.correct,
            "total": self.total,
            "macro_precision": self.macro_precision,
            "macro_recall": self.macro_recall,
            "macro_f1": self.macro_f1,
            "per_category": self.per_category,
            "calibration": self.calibration,
            "confusion_matrix": self.confusion_matrix,
            "common_mistakes": self.common_mistakes,
            "mistake_examples": self.mistake_examples,
            "weak_categories": self.weak_categories,
            "avg_confidence": self.avg_confidence,
        }


@dataclass
class ToolSelectorEvalReport:
    precision_at_1: float = 0.0
    precision_at_3: float = 0.0
    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    f1_at_3: float = 0.0
    exact_match_rate: float = 0.0
    per_tool: dict[str, dict[str, float]] = field(default_factory=dict)
    calibration: list[dict] = field(default_factory=list)
    total_examples: int = 0

    def to_dict(self) -> dict:
        return {
            "precision@1": self.precision_at_1,
            "precision@3": self.precision_at_3,
            "recall@1": self.recall_at_1,
            "recall@3": self.recall_at_3,
            "f1@3": self.f1_at_3,
            "exact_match_rate": self.exact_match_rate,
            "per_tool": self.per_tool,
            "calibration": self.calibration,
            "total_examples": self.total_examples,
        }


class IntentEvaluator:
    def evaluate(
        self,
        model: IntentModel,
        texts: list[str],
        labels: list[str],
    ) -> IntentEvalReport:
        all_classes = sorted(set(labels))
        correct = 0
        total = len(texts)
        confusion: dict[str, dict[str, int]] = {c: {c2: 0 for c2 in all_classes} for c in all_classes}
        per_category: dict[str, dict[str, int]] = {}
        confidences: list[float] = []
        correctly_confident: list[bool] = []
        mistakes: list[dict] = []

        for text, expected in zip(texts, labels):
            predicted, confidence = model.predict_with_confidence(text)
            confidences.append(confidence)
            if predicted == expected:
                correct += 1
                correctly_confident.append(True)
            else:
                correctly_confident.append(False)
                mistakes.append({
                    "text": text[:80],
                    "expected": expected,
                    "predicted": predicted,
                    "confidence": round(confidence, 4),
                })
            confusion[expected][predicted] += 1
            if expected not in per_category:
                per_category[expected] = {"correct": 0, "total": 0}
            per_category[expected]["total"] += 1
            if predicted == expected:
                per_category[expected]["correct"] += 1

        all_classes = sorted(set(labels))
        category_metrics = {}
        for cat in all_classes:
            tp = confusion[cat][cat]
            fp = sum(confusion[other][cat] for other in all_classes if other != cat)
            fn = sum(confusion[cat][other] for other in all_classes if other != cat)
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            support = per_category.get(cat, {}).get("total", 0)
            cat_acc = per_category.get(cat, {}).get("correct", 0) / support if support > 0 else 0.0
            category_metrics[cat] = {
                "accuracy": round(cat_acc, 4),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1, 4),
                "support": support,
            }

        macro_precision = sum(m["precision"] for m in category_metrics.values()) / len(category_metrics) if category_metrics else 0.0
        macro_recall = sum(m["recall"] for m in category_metrics.values()) / len(category_metrics) if category_metrics else 0.0
        macro_f1 = sum(m["f1_score"] for m in category_metrics.values()) / len(category_metrics) if category_metrics else 0.0

        calibration_buckets = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        calibration: list[dict] = []
        for i in range(len(calibration_buckets) - 1):
            lo, hi = calibration_buckets[i], calibration_buckets[i + 1]
            bucket_conf = [c for c in confidences if lo <= c < hi]
            bucket_correct = [cc for c, cc in zip(confidences, correctly_confident) if lo <= c < hi]
            if bucket_conf:
                calibration.append({
                    "bucket": f"{lo:.1f}-{hi:.1f}",
                    "count": len(bucket_conf),
                    "avg_confidence": round(sum(bucket_conf) / len(bucket_conf), 4),
                    "accuracy": round(sum(bucket_correct) / len(bucket_conf), 4) if bucket_correct else 0.0,
                })

        mistake_pairs: dict[str, int] = {}
        for m in mistakes:
            pair = f"{m['expected']} -> {m['predicted']}"
            mistake_pairs[pair] = mistake_pairs.get(pair, 0) + 1
        sorted_mistakes = sorted(mistake_pairs.items(), key=lambda x: -x[1])
        common_mistakes = [{"from_to": pair, "count": count} for pair, count in sorted_mistakes[:10]]

        accuracy = correct / total if total > 0 else 0.0
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return IntentEvalReport(
            accuracy=round(accuracy, 4),
            correct=correct,
            total=total,
            macro_precision=round(macro_precision, 4),
            macro_recall=round(macro_recall, 4),
            macro_f1=round(macro_f1, 4),
            per_category=category_metrics,
            calibration=calibration,
            confusion_matrix={c1: {c2: confusion[c1][c2] for c2 in all_classes} for c1 in all_classes},
            common_mistakes=common_mistakes,
            mistake_examples=mistakes[:10],
            weak_categories=[cat for cat, m in category_metrics.items() if m.get("f1_score", 1.0) < 0.7],
            avg_confidence=round(avg_conf, 4),
        )


class ToolSelectorEvaluator:
    def evaluate(
        self,
        model: ToolSelectorModel,
        texts: list[str],
        targets: list[list[str]],
    ) -> ToolSelectorEvalReport:
        n = len(texts)
        if n == 0:
            return ToolSelectorEvalReport()

        all_predicted = [model.predict(text) for text in texts]
        all_probs = [model.predict_with_confidence(text) for text in texts]

        p1 = [ToolSelectionMetrics.tool_precision_at_k(pred, tgt, k=1) for pred, tgt in zip(all_predicted, targets)]
        p3 = [ToolSelectionMetrics.tool_precision_at_k(pred, tgt, k=3) for pred, tgt in zip(all_predicted, targets)]
        r1 = [ToolSelectionMetrics.tool_recall_at_k(pred, tgt, k=1) for pred, tgt in zip(all_predicted, targets)]
        r3 = [ToolSelectionMetrics.tool_recall_at_k(pred, tgt, k=3) for pred, tgt in zip(all_predicted, targets)]
        exact = [ToolSelectionMetrics.exact_match(pred, tgt) for pred, tgt in zip(all_predicted, targets)]
        f1_list = [ToolSelectionMetrics.tool_f1_at_k(pred, tgt, k=3) for pred, tgt in zip(all_predicted, targets)]

        tool_tp: dict[str, int] = defaultdict(int)
        tool_fp: dict[str, int] = defaultdict(int)
        tool_fn: dict[str, int] = defaultdict(int)
        for pred, tgt in zip(all_predicted, targets):
            pred_set = set(pred)
            tgt_set = set(tgt)
            for t in model.tool_names:
                if t in pred_set and t in tgt_set:
                    tool_tp[t] += 1
                elif t in pred_set and t not in tgt_set:
                    tool_fp[t] += 1
                elif t not in pred_set and t in tgt_set:
                    tool_fn[t] += 1

        per_tool: dict[str, dict[str, float]] = {}
        for t in model.tool_names:
            tp = tool_tp.get(t, 0)
            fp = tool_fp.get(t, 0)
            fn = tool_fn.get(t, 0)
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            per_tool[t] = {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}

        bucket_size = 0.1
        buckets: dict[str, dict] = {}
        for probs, tgt in zip(all_probs, targets):
            for p in probs:
                bucket_key = f"{p.confidence - (p.confidence % bucket_size):.1f}-{p.confidence - (p.confidence % bucket_size) + bucket_size:.1f}"
                if bucket_key not in buckets:
                    buckets[bucket_key] = {"count": 0, "correct": 0, "total_confidence": 0.0}
                buckets[bucket_key]["count"] += 1
                buckets[bucket_key]["total_confidence"] += p.confidence
                if p.tool_name in tgt:
                    buckets[bucket_key]["correct"] += 1

        calibration = [
            {
                "bucket": k,
                "count": int(v["count"]),
                "accuracy": round(v["correct"] / v["count"], 4) if v["count"] > 0 else 0.0,
                "avg_confidence": round(v["total_confidence"] / v["count"], 4) if v["count"] > 0 else 0.0,
            }
            for k, v in sorted(buckets.items())
        ]

        n = len(texts)
        return ToolSelectorEvalReport(
            precision_at_1=round(sum(p1) / n, 4),
            precision_at_3=round(sum(p3) / n, 4),
            recall_at_1=round(sum(r1) / n, 4),
            recall_at_3=round(sum(r3) / n, 4),
            f1_at_3=round(sum(f1_list) / n, 4),
            exact_match_rate=round(sum(exact) / n, 4),
            per_tool=per_tool,
            calibration=calibration,
            total_examples=n,
        )


class ModelComparison:
    def compare_intent_models(
        self,
        model_a: IntentModel,
        model_b: IntentModel,
        texts: list[str],
        labels: list[str],
    ) -> dict[str, Any]:
        eval_a = IntentEvaluator().evaluate(model_a, texts, labels)
        eval_b = IntentEvaluator().evaluate(model_b, texts, labels)
        return {
            "model_a": eval_a.to_dict(),
            "model_b": eval_b.to_dict(),
            "delta": {
                "accuracy": round(eval_b.accuracy - eval_a.accuracy, 4),
                "macro_f1": round(eval_b.macro_f1 - eval_a.macro_f1, 4),
            },
        }

    def compare_tool_selector_models(
        self,
        model_a: ToolSelectorModel,
        model_b: ToolSelectorModel,
        texts: list[str],
        targets: list[list[str]],
    ) -> dict[str, Any]:
        eval_a = ToolSelectorEvaluator().evaluate(model_a, texts, targets)
        eval_b = ToolSelectorEvaluator().evaluate(model_b, texts, targets)
        return {
            "model_a": eval_a.to_dict(),
            "model_b": eval_b.to_dict(),
            "delta": {
                "precision@1": round(eval_b.precision_at_1 - eval_a.precision_at_1, 4),
                "recall@3": round(eval_b.recall_at_3 - eval_a.recall_at_3, 4),
            },
        }
