"""Benchmark runner — evaluates v2 micro-models against v1 models and heuristic baseline.

Measures intent accuracy, tool selector precision@1/@3, latency, and estimated LLM calls avoided.
Saves structured reports to ``backend/data/reports/``.

Usage:
    python -m veyron.intelligence.training.run_benchmark
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from veyron.config import DATA_DIR
from veyron.intelligence.intent.model import IntentModel
from veyron.intelligence.tool_selector.model import ToolSelectorModel
from veyron.intelligence.training.benchmark_v2 import BenchmarkReportV2, BenchmarkV2
from veyron.intelligence.training.preparation.splitter import load_jsonl_as_examples
from veyron.intelligence.training.trainer_v2 import TrainingPipelineV2

logger = logging.getLogger(__name__)

SYNTHETIC_DATA_PATH = DATA_DIR / "training" / "synthetic_training_data.jsonl"
MODELS_DIR = DATA_DIR / "models"
REPORTS_DIR = DATA_DIR / "reports"


def load_v2_models() -> tuple[IntentModel, ToolSelectorModel]:
    """Load the latest v2 models from the models directory.

    Returns:
        (intent_model, tool_selector_model).

    Raises:
        FileNotFoundError: if either model file is not found.
    """
    intent_path = MODELS_DIR / "intent_classifier.pkl"
    ts_path = MODELS_DIR / "tool_selector.pkl"

    if not intent_path.exists():
        raise FileNotFoundError(f"intent model not found at {intent_path}")
    if not ts_path.exists():
        raise FileNotFoundError(f"tool selector model not found at {ts_path}")

    intent_model = IntentModel()
    intent_model.load(str(intent_path))
    logger.info("Loaded intent model from %s", intent_path)

    ts_model = ToolSelectorModel()
    ts_model.load(str(ts_path))
    logger.info("Loaded tool selector model from %s", ts_path)

    return intent_model, ts_model


def run_benchmark(dataset_path: str | Path | None = None) -> BenchmarkReportV2:
    """Run the full v2 benchmark.

    Trains fresh v1 models from the dataset for comparison, then runs
    the benchmark comparing v2 (loaded from disk) vs v1 vs heuristic.

    Args:
        dataset_path: Path to the JSONL dataset. Defaults to synthetic data.

    Returns:
        A BenchmarkReportV2 with all measurements.
    """
    data_path = Path(dataset_path) if dataset_path else SYNTHETIC_DATA_PATH
    if not data_path.is_file():
        raise FileNotFoundError(f"Dataset not found at {data_path}")

    logger.info("Loading dataset from %s", data_path)
    dataset = load_jsonl_as_examples(str(data_path))
    logger.info("Loaded %d examples", len(dataset))

    # Load v2 models from disk.
    logger.info("Loading v2 models from %s", MODELS_DIR)
    v2_intent, v2_ts = load_v2_models()

    # Train v1 models from this dataset for comparison.
    logger.info("Training v1 models for baseline comparison ...")
    pipeline = TrainingPipelineV2()
    v1_intent, _ = pipeline.train_intent(dataset, seed=42)
    v1_ts_model = ToolSelectorModel()
    train_texts = [ex.request for ex in dataset.examples if ex.request]
    train_targets = [ex.tools_used for ex in dataset.examples if ex.request]
    v1_ts_model.fit(train_texts, train_targets)

    # Run benchmark.
    logger.info("Running v2 benchmark ...")
    benchmark = BenchmarkV2()
    report = benchmark.run(
        dataset=dataset,
        v2_intent_model=v2_intent,
        v1_intent_model=v1_intent,
        v2_ts_model=v2_ts,
        v1_ts_model=v1_ts_model,
    )

    return report


def save_reports(report: BenchmarkReportV2) -> dict[str, Path]:
    """Save benchmark reports to the reports directory.

    Args:
        report: The benchmark report to save.

    Returns:
        Dict mapping report names to file paths.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    saved: dict[str, Path] = {}

    # Full JSON report.
    json_path = REPORTS_DIR / f"benchmark_report_v2_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, default=str)
    saved["json_report"] = json_path
    logger.info("Saved JSON report to %s", json_path)

    # Text report.
    text_path = REPORTS_DIR / f"benchmark_report_v2_{timestamp}.txt"
    text_content = BenchmarkV2.print_report(report)
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text_content)
    saved["text_report"] = text_path
    logger.info("Saved text report to %s", text_path)

    # Latest symlink / copy.
    latest_json = REPORTS_DIR / "benchmark_report_v2_latest.json"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    saved["latest_report"] = latest_json

    return saved


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run Veyron v2 benchmark")
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to the JSONL dataset (default: synthetic_training_data.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for reports (default: backend/data/reports)",
    )
    args = parser.parse_args()

    if args.output:
        global REPORTS_DIR
        REPORTS_DIR = Path(args.output)

    report = run_benchmark(dataset_path=args.dataset)

    print()
    print(BenchmarkV2.print_report(report))

    saved = save_reports(report)
    print(f"\nReports saved to: {REPORTS_DIR}")
    for name, path in saved.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )
    main()
