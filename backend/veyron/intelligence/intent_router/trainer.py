"""Training pipeline for the intent router model.

Fits the multi-output TF-IDF + LogisticRegression model on derived labels,
evaluates on a held-out split (accuracy, per-class P/R/F1, confusion matrix),
and persists the model + a JSON report.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from veyron.config import DATA_DIR
from veyron.intelligence.intent_router.dataset import IntentRouterDataset
from veyron.intelligence.intent_router.evaluation import IntentRouterEvaluator
from veyron.intelligence.intent_router.model import IntentRouterModel
from veyron.intelligence.intent_router.schema import IntentRouterExample

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = DATA_DIR / "models"


def _examples_to_case_dicts(examples: list[IntentRouterExample]) -> list[dict[str, Any]]:
    return [
        {
            "request": ex.request,
            "mode": ex.mode,
            "domain": ex.domain,
            "intent_category": ex.intent_category,
        }
        for ex in examples
    ]


def train_intent_router(
    dataset: IntentRouterDataset | None = None,
    model: IntentRouterModel | None = None,
    output_dir: str | Path | None = None,
    test_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[IntentRouterModel, dict[str, Any]]:
    """Train an intent router model and produce evaluation metrics.

    Args:
        dataset: Training data. If None, builds from the synthetic dataset.
        model: Optional pre-configured model instance.
        output_dir: Directory to save the model and report.
        test_ratio: Fraction of examples held out for evaluation.
        seed: Random seed for the train/test split.

    Returns:
        (trained IntentRouterModel, metrics dict).
    """
    if dataset is None:
        dataset = IntentRouterDataset.from_synthetic()
        logger.info("loaded %d synthetic examples", len(dataset))

    train_ds, test_ds = dataset.stratified_split(test_ratio=test_ratio, seed=seed)
    logger.info("train: %d, test: %d", len(train_ds), len(test_ds))

    if model is None:
        model = IntentRouterModel()

    model.fit(
        texts=train_ds.texts(),
        modes=train_ds.modes(),
        domains=train_ds.domains(),
        intents=train_ds.intents(),
    )

    test_cases = _examples_to_case_dicts(test_ds.examples)
    evaluator = IntentRouterEvaluator()
    metrics = evaluator.evaluate_model(model, test_cases)
    logger.info(
        "intent router -> mode_acc=%.3f, domain_acc=%.3f, intent_acc=%.3f",
        metrics.get("mode_accuracy", 0.0),
        metrics.get("domain_accuracy", 0.0),
        metrics.get("intent_accuracy", 0.0),
    )

    output_path = Path(output_dir) if output_dir else DEFAULT_MODEL_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    model_path = output_path / "intent_router.pkl"
    model.save(str(model_path))
    metrics["model_path"] = str(model_path)

    report_path = output_path / "intent_router_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    logger.info("training report saved to %s", report_path)

    return model, metrics
