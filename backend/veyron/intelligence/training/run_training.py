"""Training entrypoint — loads synthetic data, trains v2 micro-models, saves artifacts.

Usage:
    python -m veyron.intelligence.training.run_training
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from veyron.config import DATA_DIR
from veyron.intelligence.training.preparation.splitter import load_jsonl_as_examples
from veyron.intelligence.training.trainer_v2 import TrainingPipelineV2

logger = logging.getLogger(__name__)

SYNTHETIC_DATA_PATH = DATA_DIR / "training" / "synthetic_training_data.jsonl"
MODEL_VERSION = "2.0.0"


def compute_dataset_hash(dataset_path: Path) -> str:
    """Compute SHA-256 hash of the full dataset file contents."""
    sha256 = hashlib.sha256()
    with open(dataset_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def run_training(output_dir: str | Path | None = None) -> dict[str, Any]:
    """Load synthetic data, train intent classifier v2 and tool selector v2, save artifacts.

    Args:
        output_dir: Directory to save models, reports, and metadata. Defaults to
            ``DATA_DIR / "models"``.

    Returns:
        A metadata dictionary containing timestamps, dataset hash, metrics,
        and saved file paths.
    """
    logger.info("=" * 60)
    logger.info("Veyron v2 Training Pipeline")
    logger.info("=" * 60)

    out = Path(output_dir) if output_dir else (DATA_DIR / "models")
    out.mkdir(parents=True, exist_ok=True)
    logger.info("Output directory: %s", out)

    # ── 1. Load dataset ──────────────────────────────────────────────────────
    logger.info("Loading synthetic training data from %s", SYNTHETIC_DATA_PATH)
    if not SYNTHETIC_DATA_PATH.is_file():
        raise FileNotFoundError(
            f"Synthetic training data not found at {SYNTHETIC_DATA_PATH}. "
            f"Run `python -m veyron.intelligence.training.generate_dataset` first."
        )
    dataset = load_jsonl_as_examples(str(SYNTHETIC_DATA_PATH))
    logger.info("Loaded %d training examples", len(dataset))

    dataset_summary = dataset.summary()
    logger.info("Dataset summary: %d total, %d successful, %d categories",
                dataset_summary["total"], dataset_summary.get("successful", 0),
                len(dataset_summary.get("categories", [])))

    # ── 2. Compute dataset hash ──────────────────────────────────────────────
    logger.info("Computing dataset content hash (SHA-256)...")
    dataset_hash = compute_dataset_hash(SYNTHETIC_DATA_PATH)
    logger.info("Dataset hash: %s", dataset_hash)

    # ── 3. Train both models ─────────────────────────────────────────────────
    pipeline = TrainingPipelineV2(output_dir=out)

    logger.info("Training intent classifier v2 ...")
    intent_model, intent_report = pipeline.train_intent(dataset, seed=42)
    logger.info("Intent classifier trained — accuracy=%.4f, macro_f1=%.4f",
                intent_report.accuracy, intent_report.macro_f1)

    logger.info("Training tool selector v2 ...")
    ts_model, ts_report = pipeline.train_tool_selector(dataset, seed=42)
    logger.info("Tool selector trained — precision@1=%.4f, recall@3=%.4f",
                ts_report.precision_at_1, ts_report.recall_at_3)

    # ── 4. Save models ───────────────────────────────────────────────────────
    logger.info("Saving trained models ...")
    saved_models = pipeline.save_models(
        intent_model=intent_model,
        tool_selector_model=ts_model,
        output_dir=out,
    )
    for name, path in saved_models.items():
        logger.info("  Saved %s -> %s", name, path)

    # ── 5. Save evaluation reports ───────────────────────────────────────────
    logger.info("Saving evaluation reports ...")
    saved_reports = pipeline.save_reports(
        intent_report=intent_report,
        ts_report=ts_report,
        output_dir=out,
    )
    for name, path in saved_reports.items():
        logger.info("  Saved %s -> %s", name, path)

    # ── 6. Build metadata ────────────────────────────────────────────────────
    training_timestamp = datetime.now(UTC).isoformat()
    intent_metrics = intent_report.to_dict()
    ts_metrics = ts_report.to_dict()

    metadata: dict[str, Any] = {
        "training_timestamp": training_timestamp,
        "dataset_hash": dataset_hash,
        "dataset_path": str(SYNTHETIC_DATA_PATH),
        "dataset_size": len(dataset),
        "model_version": MODEL_VERSION,
        "models": {
            "intent_classifier_v2": {
                "path": str(saved_models.get("intent_model", "")),
                "metrics": intent_metrics,
            },
            "tool_selector_v2": {
                "path": str(saved_models.get("tool_selector_model", "")),
                "metrics": ts_metrics,
            },
        },
        "reports": {name: str(path) for name, path in saved_reports.items()},
    }

    # ── 7. Save metadata JSON ────────────────────────────────────────────────
    metadata_path = out / "training_metadata_v2.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)
    logger.info("Saved training metadata to %s", metadata_path)

    # ── 8. Save VERSION file ─────────────────────────────────────────────────
    version_path = out / "VERSION"
    version_lines = [
        f"model_version={MODEL_VERSION}",
        f"training_timestamp={training_timestamp}",
        f"dataset_hash={dataset_hash}",
        f"dataset_size={len(dataset)}",
        f"intent_accuracy={intent_report.accuracy:.4f}",
        f"intent_macro_f1={intent_report.macro_f1:.4f}",
        f"tool_selector_precision_at_1={ts_report.precision_at_1:.4f}",
        f"tool_selector_recall_at_3={ts_report.recall_at_3:.4f}",
        "",
    ]
    with open(version_path, "w", encoding="utf-8") as f:
        f.write("\n".join(version_lines))
    logger.info("Saved VERSION file to %s", version_path)

    # ── Summary ──────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Training complete!")
    logger.info("  Intent classifier  : accuracy=%.4f  macro_f1=%.4f",
                intent_report.accuracy, intent_report.macro_f1)
    logger.info("  Tool selector      : precision@1=%.4f  recall@3=%.4f",
                ts_report.precision_at_1, ts_report.recall_at_3)
    logger.info("  Models saved to    : %s", out)
    logger.info("  Metadata           : %s", metadata_path)
    logger.info("  VERSION file       : %s", version_path)
    logger.info("=" * 60)

    return metadata


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )
    run_training()
