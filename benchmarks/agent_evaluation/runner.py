from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from veyron.config import get_settings
from veyron.core.agent import Agent
from veyron.core.evaluator import Evaluator
from veyron.db.base import init_db

from benchmarks.agent_evaluation.dataset import ALL_TASKS, BenchmarkTask
from benchmarks.agent_evaluation.metrics import AgentEvalMetrics, compute_delta, compute_metrics
from benchmarks.agent_evaluation.report import format_comparison, format_summary

logger = logging.getLogger(__name__)


@dataclass
class AgentEvalComparison:
    baseline: AgentEvalMetrics
    veyron: AgentEvalMetrics
    delta: dict[str, float | int | str] = field(default_factory=dict)
    per_task_results: dict[str, dict[str, Any]] = field(default_factory=dict)


class AgentEvalRunner:
    def __init__(
        self,
        tasks: list[BenchmarkTask] | None = None,
        output_dir: str | Path | None = None,
    ) -> None:
        self.tasks = tasks or ALL_TASKS
        self.output_dir = Path(output_dir) if output_dir else Path("benchmark_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def run_baseline(self, agent: Agent | None = None) -> AgentEvalMetrics:
        return await self._run_mode("baseline", agent)

    async def run_veyron(self, agent: Agent | None = None) -> AgentEvalMetrics:
        return await self._run_mode("veyron", agent)

    async def run_comparison(
        self,
        baseline_agent: Agent | None = None,
        veyron_agent: Agent | None = None,
    ) -> AgentEvalComparison:
        init_db()

        logger.info("=" * 60)
        logger.info("AGENT EVALUATION BENCHMARK")
        logger.info("Tasks: %d across %d categories", len(self.tasks), len({t.task.category for t in self.tasks}))
        logger.info("=" * 60)

        logger.info("Running BASELINE mode (no micro-models)...")
        baseline = await self.run_baseline(baseline_agent)

        logger.info("Running Veyron mode (full intelligence stack)...")
        veyron = await self.run_veyron(veyron_agent)

        delta = compute_delta(baseline, veyron)

        per_task_results: dict[str, dict[str, Any]] = {}
        for bt in self.tasks:
            tid = bt.task.id
            per_task_results[tid] = {
                "id": tid,
                "prompt": bt.task.prompt[:100],
                "category": bt.task.category,
                "difficulty": bt.difficulty,
                "expected_tools": list(bt.task.expected_tools),
                "expected_behavior": bt.expected_behavior,
            }

        return AgentEvalComparison(
            baseline=baseline,
            veyron=veyron,
            delta=delta,
            per_task_results=per_task_results,
        )

    async def _run_mode(
        self, mode: str, agent: Agent | None
    ) -> AgentEvalMetrics:
        settings = get_settings()
        original_value = settings.model.micro_models_enabled

        try:
            if mode == "veyron":
                settings.model.micro_models_enabled = True
            else:
                settings.model.micro_models_enabled = False

            evaluator = Evaluator(agent=agent or Agent())
            eval_tasks = [bt.task for bt in self.tasks]

            start = time.monotonic()
            results = await evaluator.run_suite(eval_tasks, include_memory_metrics=True)
            elapsed = time.monotonic() - start

            metrics = compute_metrics(results, mode)

            self._save_mode_results(mode, results, metrics, elapsed)

            logger.info(
                "%s: %d/%d passed (%.1f%%) in %.1fs",
                mode.upper(),
                metrics.successful, metrics.total,
                metrics.success_rate * 100,
                elapsed,
            )

            return metrics
        finally:
            settings.model.micro_models_enabled = original_value

    def _save_mode_results(
        self,
        mode: str,
        results: list,
        metrics: AgentEvalMetrics,
        elapsed: float,
    ) -> None:
        path = self.output_dir / f"{mode}_results.json"
        data = {
            "mode": mode,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_duration_sec": round(elapsed, 2),
            "metrics": {
                "total": metrics.total,
                "successful": metrics.successful,
                "failed": metrics.failed,
                "success_rate": metrics.success_rate,
                "avg_duration_ms": metrics.avg_duration_ms,
                "avg_iterations": metrics.avg_iterations,
                "avg_tool_calls": metrics.avg_tool_calls,
                "avg_retries": metrics.avg_retries,
                "tool_accuracy": metrics.tool_accuracy,
                "recovery_rate": metrics.recovery_rate,
            },
            "per_category": metrics.per_category,
            "failure_categories": metrics.failure_categories,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Saved %s results to %s", mode, path)

    def export(
        self,
        comparison: AgentEvalComparison,
        output_path: str | Path | None = None,
    ) -> Path:
        path = Path(output_path) if output_path else self.output_dir / "agent_eval_comparison.json"
        data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_tasks": len(self.tasks),
            "baseline": {
                "success_rate": comparison.baseline.success_rate,
                "avg_duration_ms": comparison.baseline.avg_duration_ms,
                "avg_iterations": comparison.baseline.avg_iterations,
                "avg_tool_calls": comparison.baseline.avg_tool_calls,
                "avg_retries": comparison.baseline.avg_retries,
                "tool_accuracy": comparison.baseline.tool_accuracy,
                "recovery_rate": comparison.baseline.recovery_rate,
                "total_duration_ms": comparison.baseline.total_duration_ms,
                "per_category": comparison.baseline.per_category,
            },
            "veyron": {
                "success_rate": comparison.veyron.success_rate,
                "avg_duration_ms": comparison.veyron.avg_duration_ms,
                "avg_iterations": comparison.veyron.avg_iterations,
                "avg_tool_calls": comparison.veyron.avg_tool_calls,
                "avg_retries": comparison.veyron.avg_retries,
                "tool_accuracy": comparison.veyron.tool_accuracy,
                "recovery_rate": comparison.veyron.recovery_rate,
                "total_duration_ms": comparison.veyron.total_duration_ms,
                "per_category": comparison.veyron.per_category,
            },
            "delta": comparison.delta,
            "tasks": comparison.per_task_results,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Comparison exported to %s", path)
        return path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    runner = AgentEvalRunner()
    comparison = asyncio.run(runner.run_comparison())

    print()
    print(format_summary(comparison.baseline, comparison.veyron))
    print()
    print(format_comparison(comparison))

    runner.export(comparison)


if __name__ == "__main__":
    main()
