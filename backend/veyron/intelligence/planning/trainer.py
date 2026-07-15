from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from veyron.config import DATA_DIR
from veyron.intelligence.planning.dataset import PlanningDataset
from veyron.intelligence.planning.evaluation import PlanningEvaluator
from veyron.intelligence.planning.model import PlanningModel

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = DATA_DIR / "models"


def train_planning(
    dataset: PlanningDataset | None = None,
    model: PlanningModel | None = None,
    output_dir: str | Path | None = None,
    test_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[PlanningModel, dict[str, Any]]:
    if dataset is None:
        dataset = PlanningDataset.from_synthetic()
        logger.info("loaded %d synthetic planning examples", len(dataset))

    train_ds, test_ds = dataset.stratified_split(test_ratio=test_ratio, seed=seed)
    logger.info("train: %d, test: %d", len(train_ds), len(test_ds))

    if model is None:
        model = PlanningModel()

    model.fit(
        texts=train_ds.texts(),
        plan_labels=train_ds.plan_labels(),
        steps_labels=train_ds.steps_labels(),
        categories_matrix=train_ds.categories_matrix(),
    )

    evaluator = PlanningEvaluator()
    metrics = evaluator.evaluate_model(model, test_ds)
    logger.info(
        "planning -> plan_accuracy=%.3f, steps_accuracy=%.3f, overall=%.3f",
        metrics.get("plan_accuracy", 0.0),
        metrics.get("steps_accuracy", 0.0),
        metrics.get("overall_accuracy", 0.0),
    )

    output_path = Path(output_dir) if output_dir else DEFAULT_MODEL_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    model_path = output_path / "planning.pkl"
    model.save(str(model_path))
    metrics["model_path"] = str(model_path)

    report_path = output_path / "planning_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    logger.info("training report saved to %s", report_path)

    return model, metrics
