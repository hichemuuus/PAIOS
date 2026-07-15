"""Evaluation for the parameter extraction model.

Provides per-tool and per-parameter metrics for parameter prediction quality.
Wired into the intelligence benchmark in Phase 11.5.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from veyron.intelligence.parameter_extraction.model import ParameterExtractionModel
from veyron.intelligence.parameter_extraction.schema import ParameterExample, ParameterPrediction

logger = logging.getLogger(__name__)


@dataclass
class ParameterEvalResult:
    """Evaluation result for a single parameter prediction."""

    exact_match: bool = False
    parameter_accuracy: float = 0.0
    missing_parameters: list[str] = field(default_factory=list)
    extra_parameters: list[str] = field(default_factory=list)
    value_accuracy: float = 0.0


class ParameterExtractionEvaluator:
    """Evaluator for parameter extraction quality.

    Provides:
      - Per-tool parameter accuracy
      - Exact match rate (all parameters correct)
      - Value accuracy per parameter field
      - Missing / extra parameter rates
    """

    @staticmethod
    def evaluate_prediction(
        prediction: ParameterPrediction,
        ground_truth: ParameterExample,
    ) -> ParameterEvalResult:
        """Evaluate a single parameter prediction against ground truth.

        Args:
            prediction: The model's prediction.
            ground_truth: The expected parameters.

        Returns:
            A ParameterEvalResult with basic metrics.
        """
        pred_params = set(prediction.predicted_parameters.keys())
        expected_params = set(ground_truth.expected_parameters.keys())

        missing = expected_params - pred_params
        extra = pred_params - expected_params

        common_keys = pred_params & expected_params
        value_accuracy = 0.0
        if common_keys:
            correct_values = sum(
                1 for k in common_keys
                if prediction.predicted_parameters.get(k) == ground_truth.expected_parameters.get(k)
            )
            value_accuracy = correct_values / len(common_keys)

        param_accuracy = 0.0
        if expected_params:
            param_accuracy = len(common_keys) / len(expected_params)

        exact_match = not missing and not extra

        return ParameterEvalResult(
            exact_match=exact_match,
            parameter_accuracy=param_accuracy,
            missing_parameters=sorted(missing),
            extra_parameters=sorted(extra),
            value_accuracy=value_accuracy,
        )

    def evaluate(
        self,
        predictions: list[ParameterPrediction],
        ground_truths: list[ParameterExample],
    ) -> dict[str, Any]:
        """Evaluate a batch of parameter predictions.

        Args:
            predictions: List of model predictions.
            ground_truths: List of expected examples.

        Returns:
            Aggregated metrics dict.

        Raises:
            ValueError: if the lists have different lengths.
        """
        if len(predictions) != len(ground_truths):
            raise ValueError(
                f"predictions ({len(predictions)}) and ground_truths ({len(ground_truths)}) "
                f"must have the same length"
            )

        n = len(predictions)
        if n == 0:
            return {"total": 0}

        exact_matches = 0
        total_value_accuracy = 0.0
        total_params = 0

        per_tool: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "exact": 0, "param_correct": defaultdict(int), "param_total": defaultdict(int)}
        )

        for pred, gt in zip(predictions, ground_truths):
            result = self.evaluate_prediction(pred, gt)
            if result.exact_match:
                exact_matches += 1
            total_value_accuracy += result.value_accuracy

            tool = gt.tool_name
            d = per_tool[tool]
            d["total"] += 1
            if result.exact_match:
                d["exact"] += 1
            for p, val in gt.expected_parameters.items():
                d["param_total"][p] += 1
                if pred.predicted_parameters.get(p) == val:
                    d["param_correct"][p] += 1

            total_params += len(gt.expected_parameters)

        per_tool_metrics = {}
        for tool, d in per_tool.items():
            param_metrics = {}
            for p in d["param_total"]:
                param_metrics[p] = {
                    "accuracy": round(d["param_correct"][p] / d["param_total"][p], 4) if d["param_total"][p] > 0 else 0.0,
                    "total": d["param_total"][p],
                }
            per_tool_metrics[tool] = {
                "exact_match_rate": round(d["exact"] / d["total"], 4) if d["total"] > 0 else 0.0,
                "total": d["total"],
                "parameter_accuracy": param_metrics,
            }

        return {
            "total": n,
            "exact_match_rate": round(exact_matches / n, 4) if n > 0 else 0.0,
            "avg_value_accuracy": round(total_value_accuracy / n, 4) if n > 0 else 0.0,
            "per_tool": per_tool_metrics,
        }

    def evaluate_model(
        self,
        model: ParameterExtractionModel,
        test_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Evaluate a trained ParameterExtractionModel against a list of test cases.

        Each test case must have ``request``, ``tool_name``, and
        ``expected_parameters`` keys.

        Args:
            model: A fitted ParameterExtractionModel.
            test_cases: List of dicts with request/tool_name/expected_parameters.

        Returns:
            Aggregated metrics dict with per-tool breakdown.
        """
        predictions: list[ParameterPrediction] = []
        ground_truths: list[ParameterExample] = []

        for tc in test_cases:
            request = tc["request"]
            tool_name = tc["tool_name"]

            predicted_params = model.predict(request, tool_name)

            predictions.append(ParameterPrediction(
                tool_name=tool_name,
                predicted_parameters=predicted_params,
            ))
            ground_truths.append(ParameterExample(
                request=request,
                tool_name=tool_name,
                expected_parameters=tc.get("expected_parameters", {}),
                difficulty=tc.get("difficulty", "basic"),
            ))

        return self.evaluate(predictions, ground_truths)
