from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from veyron.intelligence.error_recovery.dataset import ErrorRecoveryDataset
from veyron.intelligence.error_recovery.model import ErrorRecoveryModel
from veyron.intelligence.error_recovery.schema import RecoveryAction
from veyron.tools.base import FailureCategory, classify_failure

logger = logging.getLogger(__name__)

_HEURISTIC_ACTION_MAP: dict[str, str] = {
    FailureCategory.TIMEOUT.value: RecoveryAction.RETRY.value,
    FailureCategory.INVALID_INPUT.value: RecoveryAction.CLARIFY.value,
    FailureCategory.PERMISSION_DENIED.value: RecoveryAction.CLARIFY.value,
    FailureCategory.TOOL_ERROR.value: RecoveryAction.RETRY.value,
    FailureCategory.UNKNOWN.value: RecoveryAction.FALLBACK_LLM.value,
}


def _heuristic_predict(
    error_message: str,
    tool_name: str,
    task_context: str = "",
    previous_action: str = "none",
) -> str:
    if previous_action == "retry":
        return RecoveryAction.MODIFY_PARAMETERS.value
    fc = classify_failure(error_message).value
    return _HEURISTIC_ACTION_MAP.get(fc, RecoveryAction.FALLBACK_LLM.value)


@dataclass
class RecoveryBenchmarkResult:
    error_message: str
    tool_name: str
    expected_action: str
    model_action: str
    heuristic_action: str
    model_correct: bool
    heuristic_correct: bool
    model_confidence: float
    model_latency_ms: float
    heuristic_latency_ms: float
    model_fallback: bool


@dataclass
class RecoveryBenchmarkReport:
    total: int = 0
    model_accuracy: float = 0.0
    heuristic_accuracy: float = 0.0
    model_avg_latency_ms: float = 0.0
    heuristic_avg_latency_ms: float = 0.0
    model_fallback_rate: float = 0.0
    per_action: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "model_accuracy": self.model_accuracy,
            "heuristic_accuracy": self.heuristic_accuracy,
            "model_avg_latency_ms": self.model_avg_latency_ms,
            "heuristic_avg_latency_ms": self.heuristic_avg_latency_ms,
            "model_fallback_rate": self.model_fallback_rate,
            "per_action": self.per_action,
        }


class ErrorRecoveryBenchmark:
    def __init__(self) -> None:
        self.results: list[RecoveryBenchmarkResult] = []

    def run(
        self,
        dataset: ErrorRecoveryDataset,
        model: ErrorRecoveryModel,
    ) -> RecoveryBenchmarkReport:
        for ex in dataset.examples:
            text = (
                f"{ex.error_message} | tool: {ex.tool_name}"
                f" | context: {ex.task_context} | previous: {ex.previous_action}"
            )

            start = time.perf_counter()
            model_action, model_conf = model.predict_with_confidence(text)
            model_latency = (time.perf_counter() - start) * 1000

            start = time.perf_counter()
            heuristic_action = _heuristic_predict(
                ex.error_message, ex.tool_name, ex.task_context, ex.previous_action
            )
            heuristic_latency = (time.perf_counter() - start) * 1000

            model_correct = model_action == ex.recovery_action.value
            heuristic_correct = heuristic_action == ex.recovery_action.value

            self.results.append(RecoveryBenchmarkResult(
                error_message=ex.error_message[:60],
                tool_name=ex.tool_name,
                expected_action=ex.recovery_action.value,
                model_action=model_action,
                heuristic_action=heuristic_action,
                model_correct=model_correct,
                heuristic_correct=heuristic_correct,
                model_confidence=round(model_conf, 3),
                model_latency_ms=round(model_latency, 3),
                heuristic_latency_ms=round(heuristic_latency, 3),
                model_fallback=model_conf < 0.50,
            ))

        return self._generate_report()

    def _generate_report(self) -> RecoveryBenchmarkReport:
        n = len(self.results)
        if n == 0:
            return RecoveryBenchmarkReport()

        model_correct = sum(1 for r in self.results if r.model_correct)
        heuristic_correct = sum(1 for r in self.results if r.heuristic_correct)
        model_fallbacks = sum(1 for r in self.results if r.model_fallback)

        model_latencies = [r.model_latency_ms for r in self.results]
        heuristic_latencies = [r.heuristic_latency_ms for r in self.results]

        per_action: dict[str, dict[str, Any]] = {}
        for r in self.results:
            action = r.expected_action
            if action not in per_action:
                per_action[action] = {
                    "total": 0, "model_correct": 0, "heuristic_correct": 0,
                }
            per_action[action]["total"] += 1
            if r.model_correct:
                per_action[action]["model_correct"] += 1
            if r.heuristic_correct:
                per_action[action]["heuristic_correct"] += 1

        for action, d in per_action.items():
            d["model_accuracy"] = round(d["model_correct"] / d["total"], 4) if d["total"] else 0.0
            d["heuristic_accuracy"] = round(d["heuristic_correct"] / d["total"], 4) if d["total"] else 0.0

        return RecoveryBenchmarkReport(
            total=n,
            model_accuracy=round(model_correct / n, 4),
            heuristic_accuracy=round(heuristic_correct / n, 4),
            model_avg_latency_ms=round(sum(model_latencies) / n, 3),
            heuristic_avg_latency_ms=round(sum(heuristic_latencies) / n, 3),
            model_fallback_rate=round(model_fallbacks / n, 4),
            per_action=per_action,
        )

    @staticmethod
    def print_report(report: RecoveryBenchmarkReport) -> str:
        lines = [
            "=" * 60,
            "ERROR RECOVERY BENCHMARK",
            "=" * 60,
            f"Total samples: {report.total}",
            "",
            "--- Accuracy ---",
            f"  Learned model:  {report.model_accuracy:.2%}",
            f"  Heuristic:      {report.heuristic_accuracy:.2%}",
            f"  Improvement:    {(report.model_accuracy - report.heuristic_accuracy) * 100:+.1f}pp",
            "",
            "--- Latency ---",
            f"  Model avg:     {report.model_avg_latency_ms:.3f}ms",
            f"  Heuristic avg: {report.heuristic_avg_latency_ms:.3f}ms",
            "",
            "--- Fallback ---",
            f"  Model fallback rate: {report.model_fallback_rate:.2%}",
            "",
            "--- Per-Action ---",
        ]
        for action, d in sorted(report.per_action.items()):
            lines.append(
                f"  {action:25s}  model={d['model_accuracy']:.2%}  "
                f"heuristic={d['heuristic_accuracy']:.2%}  ({d['model_correct']}/{d['total']})"
            )
        lines.append("=" * 60)
        return "\n".join(lines)
