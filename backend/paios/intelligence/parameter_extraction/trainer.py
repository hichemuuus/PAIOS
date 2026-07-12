"""Training pipeline for the parameter extraction model.

Trains a multi-tool, multi-parameter classifier and produces per-tool,
per-parameter evaluation metrics.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from paios.config import DATA_DIR
from paios.intelligence.parameter_extraction.dataset import ParameterExtractionDataset
from paios.intelligence.parameter_extraction.model import ParameterExtractionModel

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = DATA_DIR / "models"


def train_parameter_extraction(
    dataset: ParameterExtractionDataset | None = None,
    model: ParameterExtractionModel | None = None,
    output_dir: str | Path | None = None,
    test_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[ParameterExtractionModel, dict[str, Any]]:
    """Train a parameter extraction model and produce evaluation metrics.

    Args:
        dataset: Training data. If None, loads from synthetic JSONL.
        model: Optional pre-configured model.
        output_dir: Directory to save model and metrics.
        test_ratio: Fraction held out for evaluation.
        seed: Random seed.

    Returns:
        (trained ParameterExtractionModel, metrics dict).
    """
    if dataset is None:
        path = DATA_DIR / "training" / "synthetic_training_data.jsonl"
        dataset = ParameterExtractionDataset.from_synthetic_jsonl(path)
        logger.info("loaded %d examples from %s", len(dataset), path)

    all_data = [(ex.request, ex.tool_name, ex.expected_parameters) for ex in dataset.examples]

    import random
    rng = random.Random(seed)
    indices = list(range(len(all_data)))
    rng.shuffle(indices)
    split = max(1, int(len(indices) * (1 - test_ratio)))
    train_indices = indices[:split]
    test_indices = indices[split:]

    train_data = [all_data[i] for i in train_indices]
    test_data = [all_data[i] for i in test_indices]

    logger.info("train: %d, test: %d", len(train_data), len(test_data))

    if model is None:
        model = ParameterExtractionModel()

    model.fit(train_data)

    metrics = _evaluate(model, test_data)
    logger.info(
        "parameter extraction -> exact_match=%.3f, avg_accuracy=%.3f",
        metrics["exact_match_rate"],
        metrics["avg_parameter_accuracy"],
    )

    output_path = Path(output_dir) if output_dir else DEFAULT_MODEL_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    model_path = output_path / "parameter_extraction.pkl"
    model.save(str(model_path))
    metrics["model_path"] = str(model_path)

    report_path = output_path / "parameter_extraction_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    logger.info("training report saved to %s", report_path)

    return model, metrics


def _evaluate(
    model: ParameterExtractionModel,
    test_data: list[tuple[str, str, dict[str, str]]],
) -> dict[str, Any]:
    """Evaluate parameter extraction predictions."""
    total = len(test_data)
    if total == 0:
        return {"total": 0}

    exact_matches = 0
    per_tool: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"correct": 0, "total": 0, "param_correct": defaultdict(int), "param_total": defaultdict(int)}
    )
    total_value_accuracy = 0.0

    for request, tool_name, expected in test_data:
        predicted = model.predict(request, tool_name)
        all_params = set(list(expected.keys()) + list(predicted.keys()))
        correct_params = sum(1 for p in all_params if expected.get(p) == predicted.get(p))
        param_count = len(expected) if expected else 1
        accuracy = correct_params / max(param_count, 1)
        total_value_accuracy += accuracy

        is_exact = all(expected.get(p) == predicted.get(p) for p in expected) and set(predicted.keys()) == set(expected.keys())
        if is_exact:
            exact_matches += 1

        d = per_tool[tool_name]
        d["total"] += 1
        d["correct"] += 1 if is_exact else 0
        for p in expected:
            d["param_total"][p] += 1
            if expected[p] == predicted.get(p):
                d["param_correct"][p] += 1

    per_tool_metrics = {}
    for tool, d in per_tool.items():
        param_metrics = {}
        for p in d["param_total"]:
            param_metrics[p] = {
                "accuracy": round(d["param_correct"][p] / d["param_total"][p], 4) if d["param_total"][p] > 0 else 0.0,
                "total": d["param_total"][p],
            }
        per_tool_metrics[tool] = {
            "exact_match_rate": round(d["correct"] / d["total"], 4) if d["total"] > 0 else 0.0,
            "total_examples": d["total"],
            "parameter_accuracy": param_metrics,
        }

    return {
        "total": total,
        "exact_match_rate": round(exact_matches / total, 4) if total > 0 else 0.0,
        "avg_parameter_accuracy": round(total_value_accuracy / total, 4) if total > 0 else 0.0,
        "per_tool": per_tool_metrics,
    }
