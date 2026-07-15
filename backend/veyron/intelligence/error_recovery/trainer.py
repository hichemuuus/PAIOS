from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from veyron.config import DATA_DIR
from veyron.intelligence.error_recovery.dataset import ErrorRecoveryDataset
from veyron.intelligence.error_recovery.evaluation import ErrorRecoveryEvaluator
from veyron.intelligence.error_recovery.model import ErrorRecoveryModel
from veyron.intelligence.error_recovery.schema import ErrorRecoveryExample

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = DATA_DIR / "models"


def _examples_to_case_dicts(examples: list[ErrorRecoveryExample]) -> list[dict[str, Any]]:
    return [
        {
            "error_message": ex.error_message,
            "tool_name": ex.tool_name,
            "task_context": ex.task_context,
            "previous_action": ex.previous_action,
            "recovery_action": ex.recovery_action.value,
        }
        for ex in examples
    ]


def train_error_recovery(
    dataset: ErrorRecoveryDataset | None = None,
    model: ErrorRecoveryModel | None = None,
    output_dir: str | Path | None = None,
    test_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[ErrorRecoveryModel, dict[str, Any]]:
    if dataset is None:
        dataset = ErrorRecoveryDataset.from_synthetic()
        logger.info("loaded %d synthetic error recovery examples", len(dataset))

    train_ds, test_ds = dataset.stratified_split(test_ratio=test_ratio, seed=seed)
    logger.info("train: %d, test: %d", len(train_ds), len(test_ds))

    if model is None:
        model = ErrorRecoveryModel()

    model.fit(texts=train_ds.texts(), labels=train_ds.labels())

    test_cases = _examples_to_case_dicts(test_ds.examples)
    evaluator = ErrorRecoveryEvaluator()
    metrics = evaluator.evaluate_model(model, test_cases)
    logger.info(
        "error recovery -> accuracy=%.3f, macro_f1=%.3f",
        metrics.get("accuracy", 0.0),
        metrics.get("macro_f1", 0.0),
    )

    output_path = Path(output_dir) if output_dir else DEFAULT_MODEL_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    model_path = output_path / "error_recovery.pkl"
    model.save(str(model_path))
    metrics["model_path"] = str(model_path)

    report_path = output_path / "error_recovery_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    logger.info("training report saved to %s", report_path)

    return model, metrics
