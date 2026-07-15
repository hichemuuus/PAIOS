from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from veyron.intelligence.planning.dataset import PlanningDataset
from veyron.intelligence.planning.evaluation import PlanningEvaluator
from veyron.intelligence.planning.model import PlanningModel
from veyron.intelligence.planning.schema import (
    PLANNING_CONFIDENCE_THRESHOLD,
    PlanningExample,
    PlanningPrediction,
)

logger = logging.getLogger(__name__)


def _heuristic_requires_plan(request: str) -> bool:
    req_lower = request.lower()
    complex_keywords = [
        "analyze", "refactor", "migrate", "build a", "create a", "develop",
        "implement", "research", "compare", "investigate", "set up",
        "profile", "review", "audit", "convert",
    ]
    return any(kw in req_lower for kw in complex_keywords) and len(request.split()) > 4


def _heuristic_step_count(request: str) -> int:
    if not _heuristic_requires_plan(request):
        return 0
    word_count = len(request.split())
    if word_count > 15:
        return 5
    if word_count > 10:
        return 3
    return 2


def _run_heuristic(examples: list[PlanningExample]) -> list[PlanningPrediction]:
    predictions: list[PlanningPrediction] = []
    for ex in examples:
        requires_plan = _heuristic_requires_plan(ex.request)
        steps = _heuristic_step_count(ex.request) if requires_plan else 0
        predictions.append(PlanningPrediction(
            request=ex.request,
            requires_plan=requires_plan,
            estimated_steps=steps,
            step_categories=ex.step_categories if requires_plan else [],
            confidence=0.0,
            requires_llm=False,
            fallback=True,
        ))
    return predictions


def run_benchmark(
    model: PlanningModel | None = None,
    dataset: PlanningDataset | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    if dataset is None:
        dataset = PlanningDataset.from_synthetic()

    if model is None:
        logger.info("no model provided, training on synthetic data...")
        from veyron.intelligence.planning.trainer import train_planning
        model, train_metrics = train_planning(dataset=dataset, test_ratio=0.0)

    examples = dataset.examples

    evaluator = PlanningEvaluator()

    model_preds: list[PlanningPrediction] = []
    model_latencies: list[float] = []
    for ex in examples:
        text = f"{ex.request} | intent: {ex.intent_category} | complexity: {ex.complexity}"
        t0 = time.perf_counter()
        requires_plan, estimated_steps, step_categories, plan_conf, steps_conf, overall_conf = model.predict(text)
        dt = time.perf_counter() - t0
        model_latencies.append(dt)
        model_preds.append(PlanningPrediction(
            request=ex.request,
            requires_plan=requires_plan,
            estimated_steps=estimated_steps,
            step_categories=step_categories,
            confidence=round(overall_conf, 3),
            plan_confidence=round(plan_conf, 3),
            steps_confidence=round(steps_conf, 3),
            requires_llm=overall_conf < PLANNING_CONFIDENCE_THRESHOLD,
            fallback=overall_conf < PLANNING_CONFIDENCE_THRESHOLD,
        ))

    heuristic_preds = _run_heuristic(examples)

    model_metrics = evaluator.evaluate(model_preds, examples)
    heuristic_metrics = evaluator.evaluate(heuristic_preds, examples)

    avg_model_latency = (sum(model_latencies) / len(model_latencies)) * 1000 if model_latencies else 0.0

    results: dict[str, Any] = {
        "total_examples": len(examples),
        "model": {
            "plan_accuracy": model_metrics.get("plan_accuracy", 0.0),
            "steps_accuracy": model_metrics.get("steps_accuracy", 0.0),
            "overall_accuracy": model_metrics.get("overall_accuracy", 0.0),
            "mean_category_jaccard": model_metrics.get("mean_category_jaccard", 0.0),
            "fallback_rate": model_metrics.get("fallback_rate", 0.0),
            "avg_latency_ms": round(avg_model_latency, 4),
        },
        "heuristic": {
            "plan_accuracy": heuristic_metrics.get("plan_accuracy", 0.0),
            "steps_accuracy": heuristic_metrics.get("steps_accuracy", 0.0),
            "overall_accuracy": heuristic_metrics.get("overall_accuracy", 0.0),
            "mean_category_jaccard": heuristic_metrics.get("mean_category_jaccard", 0.0),
            "fallback_rate": heuristic_metrics.get("fallback_rate", 0.0),
        },
        "improvement": {
            "plan_accuracy_pp": round(
                model_metrics.get("plan_accuracy", 0.0) - heuristic_metrics.get("plan_accuracy", 0.0), 4
            ),
            "overall_accuracy_pp": round(
                model_metrics.get("overall_accuracy", 0.0) - heuristic_metrics.get("overall_accuracy", 0.0), 4
            ),
        },
    }

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        bench_path = out_path / "planning_benchmark.json"
        with open(bench_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info("benchmark saved to %s", bench_path)

    logger.info(
        "benchmark: model plan_acc=%.3f heuristic plan_acc=%.3f (improvement %+.1fpp)",
        results["model"]["plan_accuracy"],
        results["heuristic"]["plan_accuracy"],
        results["improvement"]["plan_accuracy_pp"] * 100,
    )

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    results = run_benchmark()
    print(json.dumps(results, indent=2))
