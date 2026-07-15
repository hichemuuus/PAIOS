"""Benchmark: synthetic-trained vs real-data-trained micro-model performance.

Compares intent classifier and tool selector models trained on synthetic data
vs. real user interaction data. Reports accuracy, precision, recall, latency,
and per-category breakdown.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veyron.config import DATA_DIR
from veyron.intelligence.training.dataset import (
    TrainingDataset,
    user_interactions_to_dataset,
)
from veyron.intelligence.training.trainer_v2 import TrainingPipelineV2

logger = logging.getLogger(__name__)

SYNTHETIC_PATH = DATA_DIR / "training" / "synthetic_training_data.jsonl"


@dataclass
class BenchmarkResult:
    model_type: str
    source: str
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    latency_ms: float = 0.0
    dataset_size: int = 0
    per_category: dict[str, float] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)


def _load_synthetic_dataset() -> TrainingDataset | None:
    if not SYNTHETIC_PATH.exists():
        logger.warning("synthetic dataset not found at %s", SYNTHETIC_PATH)
        return None
    try:
        return TrainingDataset.from_jsonl(SYNTHETIC_PATH)
    except Exception as e:
        logger.warning("failed to load synthetic dataset: %s", e)
        return None


def _load_real_dataset(min_quality: float = 0.3) -> TrainingDataset | None:
    try:
        dataset = user_interactions_to_dataset(min_quality=min_quality)
        if len(dataset) < 5:
            logger.info("real dataset too small (%d examples), skipping", len(dataset))
            return None
        return dataset
    except Exception as e:
        logger.warning("failed to load real dataset: %s", e)
        return None


def _measure_latency(model, texts: list[str], n: int = 5) -> float:
    times: list[float] = []
    for text in texts[:n]:
        start = time.perf_counter()
        model.predict([text])
        times.append((time.perf_counter() - start) * 1000)
    return round(sum(times) / len(times), 3) if times else 0.0


def benchmark_intent(
    pipeline: TrainingPipelineV2,
    train_dataset: TrainingDataset,
    test_dataset: TrainingDataset,
    source: str,
) -> BenchmarkResult:
    texts = [ex.request for ex in test_dataset.examples if ex.request]
    labels = [ex.intent for ex in test_dataset.examples if ex.request]

    model, report = pipeline.train_intent(train_dataset, test_dataset)

    from veyron.intelligence.training.evaluation import IntentEvaluator
    eval_report = IntentEvaluator().evaluate(model, texts, labels)
    eval_dict = eval_report.to_dict()

    latency = _measure_latency(model, texts)

    per_cat: dict[str, float] = {}
    for cat, metrics in eval_dict.get("per_category", {}).items():
        per_cat[cat] = metrics.get("f1", 0.0)

    return BenchmarkResult(
        model_type="intent_classifier",
        source=source,
        accuracy=eval_dict.get("accuracy", 0.0),
        precision=eval_dict.get("macro_precision", 0.0),
        recall=eval_dict.get("macro_recall", 0.0),
        f1=eval_dict.get("macro_f1", 0.0),
        latency_ms=latency,
        dataset_size=len(train_dataset),
        per_category=per_cat,
        errors=eval_dict.get("common_mistakes", [])[:5],
    )


def benchmark_tool_selector(
    pipeline: TrainingPipelineV2,
    train_dataset: TrainingDataset,
    test_dataset: TrainingDataset,
    source: str,
) -> BenchmarkResult:
    texts = [ex.request for ex in test_dataset.examples if ex.request]
    targets = [ex.tools_used for ex in test_dataset.examples if ex.request]

    model, report = pipeline.train_tool_selector(train_dataset, test_dataset)

    from veyron.intelligence.training.evaluation import ToolSelectorEvaluator
    eval_report = ToolSelectorEvaluator().evaluate(model, texts, targets)
    eval_dict = eval_report.to_dict()

    latency = _measure_latency(model, texts)

    per_cat: dict[str, float] = {}
    for tool, metrics in eval_dict.get("per_tool", {}).items():
        per_cat[tool] = metrics.get("f1", 0.0)

    return BenchmarkResult(
        model_type="tool_selector",
        source=source,
        accuracy=eval_dict.get("exact_match_rate", 0.0),
        precision=eval_dict.get("precision_at_1", 0.0),
        recall=eval_dict.get("recall_at_1", 0.0),
        f1=eval_dict.get("f1_at_3", 0.0),
        latency_ms=latency,
        dataset_size=len(train_dataset),
        per_category=per_cat,
    )


def run_comparison(output_path: str | Path | None = None) -> dict[str, Any]:
    """Train and compare models on synthetic vs real data.

    Returns a dict with BenchmarkResult for each combination.
    """
    pipeline = TrainingPipelineV2()
    real_dataset = _load_real_dataset()
    synthetic_dataset = _load_synthetic_dataset()

    if synthetic_dataset is None and real_dataset is None:
        return {"error": "no datasets available for comparison"}

    test_dataset = real_dataset or synthetic_dataset
    if test_dataset is None:
        return {"error": "no test dataset available"}
    test_dataset = test_dataset.deduplicate()

    train_syn = synthetic_dataset.deduplicate() if synthetic_dataset else TrainingDataset()
    train_real = real_dataset.deduplicate() if real_dataset else TrainingDataset()

    results: dict[str, Any] = {
        "datasets": {
            "synthetic": len(train_syn),
            "real": len(train_real),
            "test": len(test_dataset),
        },
        "intent_classifier": [],
        "tool_selector": [],
    }

    if len(train_syn) >= 10:
        logger.info("benchmarking intent_classifier on synthetic data (%d examples)...", len(train_syn))
        syn_result = benchmark_intent(pipeline, train_syn, test_dataset, "synthetic")
        results["intent_classifier"].append({
            "source": "synthetic",
            "accuracy": syn_result.accuracy,
            "precision": syn_result.precision,
            "recall": syn_result.recall,
            "f1": syn_result.f1,
            "latency_ms": syn_result.latency_ms,
            "dataset_size": syn_result.dataset_size,
            "per_category": syn_result.per_category,
        })

        logger.info("benchmarking tool_selector on synthetic data (%d examples)...", len(train_syn))
        ts_result = benchmark_tool_selector(pipeline, train_syn, test_dataset, "synthetic")
        results["tool_selector"].append({
            "source": "synthetic",
            "exact_match_rate": ts_result.accuracy,
            "precision_at_1": ts_result.precision,
            "recall_at_1": ts_result.recall,
            "f1_at_3": ts_result.f1,
            "latency_ms": ts_result.latency_ms,
            "dataset_size": ts_result.dataset_size,
            "per_tool": ts_result.per_category,
        })

    if len(train_real) >= 5:
        logger.info("benchmarking intent_classifier on real data (%d examples)...", len(train_real))
        real_result = benchmark_intent(pipeline, train_real, test_dataset, "real")
        results["intent_classifier"].append({
            "source": "real",
            "accuracy": real_result.accuracy,
            "precision": real_result.precision,
            "recall": real_result.recall,
            "f1": real_result.f1,
            "latency_ms": real_result.latency_ms,
            "dataset_size": real_result.dataset_size,
            "per_category": real_result.per_category,
        })

        logger.info("benchmarking tool_selector on real data (%d examples)...", len(train_real))
        ts_result = benchmark_tool_selector(pipeline, train_real, test_dataset, "real")
        results["tool_selector"].append({
            "source": "real",
            "exact_match_rate": ts_result.accuracy,
            "precision_at_1": ts_result.precision,
            "recall_at_1": ts_result.recall,
            "f1_at_3": ts_result.f1,
            "latency_ms": ts_result.latency_ms,
            "dataset_size": ts_result.dataset_size,
            "per_tool": ts_result.per_category,
        })

    if len(train_syn) >= 10 and len(train_real) >= 5:
        merged = train_syn.merge(train_real)
        logger.info("benchmarking on merged data (%d examples)...", len(merged))
        merged_intent = benchmark_intent(pipeline, merged, test_dataset, "merged")
        results["intent_classifier"].append({
            "source": "merged",
            "accuracy": merged_intent.accuracy,
            "precision": merged_intent.precision,
            "recall": merged_intent.recall,
            "f1": merged_intent.f1,
            "latency_ms": merged_intent.latency_ms,
            "dataset_size": merged_intent.dataset_size,
            "per_category": merged_intent.per_category,
        })
        merged_ts = benchmark_tool_selector(pipeline, merged, test_dataset, "merged")
        results["tool_selector"].append({
            "source": "merged",
            "exact_match_rate": merged_ts.accuracy,
            "precision_at_1": merged_ts.precision,
            "recall_at_1": merged_ts.recall,
            "f1_at_3": merged_ts.f1,
            "latency_ms": merged_ts.latency_ms,
            "dataset_size": merged_ts.dataset_size,
            "per_tool": merged_ts.per_category,
        })

    results["summary"] = _build_summary(results)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info("benchmark comparison saved to %s", path)

    return results


def _build_summary(results: dict) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for model_type, entries in results.items():
        if model_type in ("datasets", "summary", "error"):
            continue
        for entry in entries:
            key = f"{model_type}_{entry['source']}"
            summary[key] = {
                "dataset_size": entry["dataset_size"],
                "accuracy": entry.get("accuracy") or entry.get("exact_match_rate", 0.0),
                "latency_ms": entry.get("latency_ms", 0.0),
            }
    return summary


def print_comparison(results: dict[str, Any]) -> str:
    lines = [
        "=" * 70,
        "REAL vs SYNTHETIC — MODEL COMPARISON",
        "=" * 70,
        "",
        f"  Datasets:  synthetic={results.get('datasets', {}).get('synthetic', 0)}  "
        f"real={results.get('datasets', {}).get('real', 0)}  "
        f"test={results.get('datasets', {}).get('test', 0)}",
        "",
    ]

    for model_type in ["intent_classifier", "tool_selector"]:
        entries = results.get(model_type, [])
        if not entries:
            continue
        label = model_type.replace("_", " ").title()
        lines.append(f"  [{label}]")
        lines.append(f"  {'Source':<12s} {'Size':>6s} {'Acc':>8s} {'P@1':>8s} {'R@1':>8s} {'F1':>8s} {'Lat(ms)':>10s}")
        lines.append(f"  {'-'*56}")
        for e in entries:
            src = e["source"]
            sz = e["dataset_size"]
            acc = e.get("accuracy") or e.get("exact_match_rate", 0.0)
            prec = e.get("precision") or e.get("precision_at_1", 0.0)
            rec = e.get("recall") or e.get("recall_at_1", 0.0)
            f1 = e.get("f1") or e.get("f1_at_3", 0.0)
            lat = e.get("latency_ms", 0.0)
            lines.append(f"  {src:<12s} {sz:>6d} {acc:>7.1%} {prec:>7.1%} {rec:>7.1%} {f1:>7.1%} {lat:>9.2f}")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    output = DATA_DIR / "training" / "benchmark_comparison.json"
    results = run_comparison(output_path=output)
    if "error" in results:
        logger.error("benchmark failed: %s", results["error"])
        print(results["error"])
        return 1
    print(print_comparison(results))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
