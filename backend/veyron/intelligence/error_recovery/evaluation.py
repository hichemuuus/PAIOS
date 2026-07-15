from __future__ import annotations

from typing import Any

from veyron.intelligence.error_recovery.model import ErrorRecoveryModel
from veyron.intelligence.error_recovery.schema import (
    RECOVERY_CONFIDENCE_THRESHOLD,
    ErrorRecoveryExample,
    ErrorRecoveryPrediction,
    RecoveryAction,
)


def _per_class_metrics(
    true_labels: list[str],
    pred_labels: list[str],
) -> dict[str, dict[str, float]]:
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


class ErrorRecoveryEvaluator:
    @staticmethod
    def evaluate_prediction(
        prediction: ErrorRecoveryPrediction,
        ground_truth: ErrorRecoveryExample,
    ) -> dict[str, Any]:
        return {
            "action_correct": prediction.recovery_action == ground_truth.recovery_action,
            "requires_llm": prediction.requires_llm,
            "fallback": prediction.fallback,
        }

    def evaluate(
        self,
        predictions: list[ErrorRecoveryPrediction],
        ground_truths: list[ErrorRecoveryExample],
    ) -> dict[str, Any]:
        if len(predictions) != len(ground_truths):
            raise ValueError(
                f"predictions/ground_truths length mismatch: {len(predictions)} != {len(ground_truths)}"
            )
        n = len(predictions)
        if n == 0:
            return {"total": 0}

        true_labels: list[str] = []
        pred_labels: list[str] = []

        correct = 0
        fallback_count = 0
        llm_count = 0

        for pred, gt in zip(predictions, ground_truths):
            true_labels.append(gt.recovery_action.value)
            pred_labels.append(pred.recovery_action.value)
            if pred.recovery_action == gt.recovery_action:
                correct += 1
            if pred.fallback:
                fallback_count += 1
            if pred.requires_llm:
                llm_count += 1

        result: dict[str, Any] = {
            "total": n,
            "accuracy": round(correct / n, 4),
            "fallback_rate": round(fallback_count / n, 4),
            "llm_call_rate": round(llm_count / n, 4),
            "per_class": _per_class_metrics(true_labels, pred_labels),
            "confusion_matrix": _confusion_matrix(true_labels, pred_labels),
            "avg_confidence": 0.0,
        }

        if predictions:
            result["avg_confidence"] = round(
                sum(p.confidence for p in predictions) / n, 4
            )

        return result

    def evaluate_model(
        self,
        model: ErrorRecoveryModel,
        test_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if model is None or not getattr(model, "fitted", False):
            return {"available": False, "total": len(test_cases), "note": "model not available"}

        predictions: list[ErrorRecoveryPrediction] = []
        ground_truths: list[ErrorRecoveryExample] = []

        for tc in test_cases:
            text = (
                f"{tc.get('error_message', '')} | tool: {tc.get('tool_name', '')}"
                f" | context: {tc.get('task_context', '')}"
                f" | previous: {tc.get('previous_action', '')}"
            )
            action_str, confidence = model.predict_with_confidence(text)

            try:
                action = RecoveryAction(action_str)
            except ValueError:
                action = RecoveryAction.FALLBACK_LLM
                confidence = 0.0

            fallback = confidence < RECOVERY_CONFIDENCE_THRESHOLD
            requires_llm = fallback or action == RecoveryAction.FALLBACK_LLM

            predictions.append(ErrorRecoveryPrediction(
                error_message=tc.get("error_message", ""),
                tool_name=tc.get("tool_name", ""),
                recovery_action=action,
                confidence=round(confidence, 3),
                requires_llm=requires_llm,
                fallback=fallback,
            ))
            ground_truths.append(ErrorRecoveryExample(
                error_message=tc.get("error_message", ""),
                tool_name=tc.get("tool_name", ""),
                task_context=tc.get("task_context", ""),
                previous_action=tc.get("previous_action", "none"),
                recovery_action=RecoveryAction(tc.get("recovery_action", "fallback_llm")),
            ))

        result = self.evaluate(predictions, ground_truths)
        result["available"] = True
        return result
