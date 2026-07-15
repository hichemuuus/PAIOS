from __future__ import annotations

from typing import Any

from veyron.intelligence.planning.dataset import PlanningDataset
from veyron.intelligence.planning.model import PlanningModel
from veyron.intelligence.planning.schema import (
    PlanningExample,
    PlanningPrediction,
)


class PlanningEvaluator:
    @staticmethod
    def evaluate_prediction(
        prediction: PlanningPrediction,
        ground_truth: PlanningExample,
    ) -> dict[str, Any]:
        plan_correct = prediction.requires_plan == ground_truth.requires_plan
        steps_correct = prediction.estimated_steps == ground_truth.estimated_steps

        gt_cats = set(ground_truth.step_categories)
        pred_cats = set(prediction.step_categories)
        intersection = gt_cats & pred_cats
        union = gt_cats | pred_cats
        cat_jaccard = len(intersection) / len(union) if union else 1.0

        return {
            "plan_correct": plan_correct,
            "steps_correct": steps_correct,
            "category_jaccard": cat_jaccard,
        }

    def evaluate(
        self,
        predictions: list[PlanningPrediction],
        ground_truths: list[PlanningExample],
    ) -> dict[str, Any]:
        if len(predictions) != len(ground_truths):
            raise ValueError(
                f"predictions/ground_truths length mismatch: {len(predictions)} != {len(ground_truths)}"
            )
        n = len(predictions)
        if n == 0:
            return {"total": 0}

        plan_correct = 0
        steps_correct = 0
        category_jaccards: list[float] = []
        fallback_count = 0
        llm_count = 0
        total_true_pos = 0
        total_pred_pos = 0
        total_actual_pos = 0

        for pred, gt in zip(predictions, ground_truths):
            if pred.requires_plan == gt.requires_plan:
                plan_correct += 1
            if pred.estimated_steps == gt.estimated_steps:
                steps_correct += 1

            gt_cats = set(gt.step_categories)
            pred_cats = set(pred.step_categories)
            intersection = gt_cats & pred_cats
            union = gt_cats | pred_cats
            category_jaccards.append(len(intersection) / len(union) if union else 1.0)

            if pred.fallback:
                fallback_count += 1
            if pred.requires_llm:
                llm_count += 1

            total_true_pos += len(intersection)
            total_pred_pos += len(pred_cats)
            total_actual_pos += len(gt_cats)

        return {
            "total": n,
            "plan_accuracy": round(plan_correct / n, 4),
            "steps_accuracy": round(steps_correct / n, 4),
            "overall_accuracy": round(
                (plan_correct + steps_correct) / (2 * n), 4
            ),
            "mean_category_jaccard": round(
                sum(category_jaccards) / n, 4
            ) if category_jaccards else 0.0,
            "fallback_rate": round(fallback_count / n, 4),
            "llm_call_rate": round(llm_count / n, 4),
        }

    def evaluate_model(
        self,
        model: PlanningModel,
        dataset: PlanningDataset,
    ) -> dict[str, Any]:
        if model is None or not getattr(model, "fitted", False):
            return {"available": False, "total": len(dataset), "note": "model not available"}

        predictions: list[PlanningPrediction] = []
        ground_truths: list[PlanningExample] = []

        for ex in dataset.examples:
            text = f"{ex.request} | intent: {ex.intent_category} | complexity: {ex.complexity}"
            requires_plan, estimated_steps, step_categories, plan_conf, steps_conf, overall_conf = model.predict(text)

            fallback = overall_conf < 0.50
            requires_llm = fallback

            predictions.append(PlanningPrediction(
                request=ex.request,
                requires_plan=requires_plan,
                estimated_steps=estimated_steps,
                step_categories=step_categories,
                confidence=round(overall_conf, 3),
                plan_confidence=round(plan_conf, 3),
                steps_confidence=round(steps_conf, 3),
                requires_llm=requires_llm,
                fallback=fallback,
            ))
            ground_truths.append(ex)

        result = self.evaluate(predictions, ground_truths)
        result["available"] = True
        return result
