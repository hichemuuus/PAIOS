"""Evaluation for the intent router micro-model.

Provides per-field accuracy, precision/recall/F1 per class, confusion matrices,
fallback rate estimation, and aggregate comparison against the heuristic router.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from veyron.intelligence.intent_router.model import IntentRouterModel
from veyron.intelligence.intent_router.schema import (
    DOMAIN_THRESHOLD,
    INTENT_THRESHOLD,
    MODE_THRESHOLD,
    IntentRouterExample,
    IntentRouterPrediction,
)


def _per_class_metrics(
    true_labels: list[str],
    pred_labels: list[str],
) -> dict[str, dict[str, float]]:
    """Compute precision, recall, F1 per class."""
    classes = sorted(set(true_labels) | set(pred_labels))
    results: dict[str, dict[str, float]] = {}
    for cls in classes:
        tp = sum(1 for t, p in zip(true_labels, pred_labels) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(true_labels, pred_labels) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(true_labels, pred_labels) if t == cls and p != cls)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        results[cls] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "support": sum(1 for t in true_labels if t == cls),
        }
    return results


def _confusion_matrix(
    true_labels: list[str],
    pred_labels: list[str],
) -> dict[str, dict[str, int]]:
    classes = sorted(set(true_labels) | set(pred_labels))
    matrix: dict[str, dict[str, int]] = {c: {c2: 0 for c2 in classes} for c in classes}
    for t, p in zip(true_labels, pred_labels):
        if t in matrix and p in matrix[t]:
            matrix[t][p] += 1
    return matrix


class IntentRouterEvaluator:
    """Evaluator for the intent router model across all three outputs."""

    @staticmethod
    def evaluate_prediction(
        prediction: IntentRouterPrediction,
        ground_truth: IntentRouterExample,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "mode_correct": prediction.mode == ground_truth.mode,
            "domain_correct": prediction.domain == ground_truth.domain,
            "intent_correct": prediction.intent_category == ground_truth.intent_category,
            "all_correct": (
                prediction.mode == ground_truth.mode
                and prediction.domain == ground_truth.domain
                and prediction.intent_category == ground_truth.intent_category
            ),
            "requires_llm": prediction.requires_llm,
            "fallback_fields": list(prediction.fallback_fields),
        }
        return result

    def evaluate(
        self,
        predictions: list[IntentRouterPrediction],
        ground_truths: list[IntentRouterExample],
    ) -> dict[str, Any]:
        if len(predictions) != len(ground_truths):
            raise ValueError(
                f"predictions/ground_truths length mismatch: {len(predictions)} != {len(ground_truths)}"
            )
        n = len(predictions)
        if n == 0:
            return {"total": 0}

        mode_true: list[str] = []
        mode_pred: list[str] = []
        domain_true: list[str] = []
        domain_pred: list[str] = []
        intent_true: list[str] = []
        intent_pred: list[str] = []

        all_correct = 0
        fallback_count = 0
        per_field_fallback: dict[str, int] = Counter()

        for pred, gt in zip(predictions, ground_truths):
            mode_true.append(gt.mode)
            mode_pred.append(pred.mode)
            domain_true.append(gt.domain)
            domain_pred.append(pred.domain)
            intent_true.append(gt.intent_category)
            intent_pred.append(pred.intent_category)

            if pred.mode == gt.mode and pred.domain == gt.domain and pred.intent_category == gt.intent_category:
                all_correct += 1
            if pred.requires_llm:
                fallback_count += 1
            for field in pred.fallback_fields:
                per_field_fallback[field] += 1

        mode_correct = sum(1 for t, p in zip(mode_true, mode_pred) if t == p)
        domain_correct = sum(1 for t, p in zip(domain_true, domain_pred) if t == p)
        intent_correct = sum(1 for t, p in zip(intent_true, intent_pred) if t == p)

        result: dict[str, Any] = {
            "total": n,
            "mode_accuracy": round(mode_correct / n, 4),
            "domain_accuracy": round(domain_correct / n, 4),
            "intent_accuracy": round(intent_correct / n, 4),
            "overall_accuracy": round(all_correct / n, 4),
            "fallback_rate": round(fallback_count / n, 4),
            "mode_per_class": _per_class_metrics(mode_true, mode_pred),
            "domain_per_class": _per_class_metrics(domain_true, domain_pred),
            "intent_per_class": _per_class_metrics(intent_true, intent_pred),
            "mode_confusion_matrix": _confusion_matrix(mode_true, mode_pred),
            "domain_confusion_matrix": _confusion_matrix(domain_true, domain_pred),
            "intent_confusion_matrix": _confusion_matrix(intent_true, intent_pred),
            "per_field_fallback": dict(per_field_fallback),
            "avg_mode_confidence": 0.0,
            "avg_domain_confidence": 0.0,
            "avg_intent_confidence": 0.0,
        }

        if predictions:
            result["avg_mode_confidence"] = round(
                sum(p.mode_confidence for p in predictions) / n, 4
            )
            result["avg_domain_confidence"] = round(
                sum(p.domain_confidence for p in predictions) / n, 4
            )
            result["avg_intent_confidence"] = round(
                sum(p.intent_confidence for p in predictions) / n, 4
            )

        return result

    def evaluate_model(
        self,
        model: IntentRouterModel,
        test_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Evaluate a fitted model on a list of test case dicts.

        Each case dict has the shape::
            {
                "request": "...",
                "mode": "react",
                "domain": "filesystem",
                "intent_category": "file_operation",
            }

        Returns aggregate metrics dict plus ``available: True/False``.
        """
        if model is None or not getattr(model, "fitted", False):
            return {"available": False, "total": len(test_cases), "note": "model not available"}

        predictions: list[IntentRouterPrediction] = []
        ground_truths: list[IntentRouterExample] = []

        for tc in test_cases:
            text = tc.get("request", "")
            confidences = model.predict_with_confidence(text)

            mode_pred, mode_conf = confidences.get("mode", ("react", 0.0))
            domain_pred, domain_conf = confidences.get("domain", ("general", 0.0))
            intent_pred, intent_conf = confidences.get("intent_category", ("conversation", 0.0))

            fallback_fields: list[str] = []
            if mode_conf < MODE_THRESHOLD:
                fallback_fields.append("mode")
            if domain_conf < DOMAIN_THRESHOLD:
                fallback_fields.append("domain")
            if intent_conf < INTENT_THRESHOLD:
                fallback_fields.append("intent_category")

            requires_llm = len(fallback_fields) >= 2 or (
                len(fallback_fields) == 1 and mode_conf < MODE_THRESHOLD
            )

            predictions.append(IntentRouterPrediction(
                request=text,
                mode=mode_pred,
                mode_confidence=mode_conf,
                domain=domain_pred,
                domain_confidence=domain_conf,
                intent_category=intent_pred,
                intent_confidence=intent_conf,
                requires_llm=requires_llm,
                fallback_fields=fallback_fields,
            ))
            ground_truths.append(IntentRouterExample(
                request=text,
                mode=tc.get("mode", "react"),
                domain=tc.get("domain", "general"),
                intent_category=tc.get("intent_category", "conversation"),
            ))

        result = self.evaluate(predictions, ground_truths)
        result["available"] = True
        return result
