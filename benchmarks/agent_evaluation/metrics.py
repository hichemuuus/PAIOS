from __future__ import annotations

from dataclasses import dataclass, field

from veyron.core.evaluator import EvalResult


@dataclass
class AgentEvalMetrics:
    mode: str
    total: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    avg_iterations: float = 0.0
    avg_tool_calls: float = 0.0
    avg_retries: float = 0.0
    avg_replans: float = 0.0
    tool_accuracy: float = 0.0
    partial_success: int = 0
    recovery_rate: float = 0.0
    total_duration_ms: int = 0
    per_category: dict[str, dict[str, float]] = field(default_factory=dict)
    failure_categories: dict[str, int] = field(default_factory=dict)
    error_counts: dict[str, int] = field(default_factory=dict)


def _classify_error(error: str | None) -> str:
    if error is None:
        return "none"
    err_lower = error.lower()
    if "timeout" in err_lower:
        return "timeout"
    if "permission" in err_lower or "denied" in err_lower:
        return "permission"
    if "not found" in err_lower or "does not exist" in err_lower:
        return "not_found"
    if "invalid" in err_lower or "validation" in err_lower:
        return "invalid_input"
    if "cancelled" in err_lower:
        return "cancelled"
    if "exception" in err_lower or "traceback" in err_lower or "error" in err_lower:
        return "exception"
    return "unknown"


def compute_metrics(results: list[EvalResult], mode: str) -> AgentEvalMetrics:
    total = len(results)
    if total == 0:
        return AgentEvalMetrics(mode=mode)

    successful = sum(1 for r in results if r.success)
    failed = total - successful

    avg_duration = sum(r.duration_ms for r in results) / total
    avg_iters = sum(r.iterations for r in results) / total
    avg_tools = sum(r.tool_calls_count for r in results) / total
    avg_retries = sum(r.retry_count for r in results) / total
    avg_replans = sum(r.replan_count for r in results) / total

    total_duration = sum(r.duration_ms for r in results)

    tool_accuracy = _compute_tool_accuracy(results)

    partial = sum(
        1 for r in results
        if not r.success and r.tool_calls_count > 0
    )

    recovery_tasks = [r for r in results if "recovery" in r.details.get("expected_behavior", "")]
    recovery_rate = (
        sum(1 for r in recovery_tasks if r.success) / len(recovery_tasks)
        if recovery_tasks else 0.0
    )

    failure_cats: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    for r in results:
        cat = _classify_error(r.error)
        failure_cats[cat] = failure_cats.get(cat, 0) + 1
        if r.error:
            error_key = r.error[:80]
            error_counts[error_key] = error_counts.get(error_key, 0) + 1

    per_category: dict[str, dict[str, float]] = {}
    by_cat: dict[str, list[EvalResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)
    for cat, cat_results in by_cat.items():
        cat_total = len(cat_results)
        cat_pass = sum(1 for r in cat_results if r.success)
        per_category[cat] = {
            "total": cat_total,
            "passed": cat_pass,
            "failed": cat_total - cat_pass,
            "pass_rate": round(cat_pass / cat_total, 3) if cat_total > 0 else 0.0,
            "avg_duration_ms": round(sum(r.duration_ms for r in cat_results) / cat_total, 1),
            "avg_tool_calls": round(sum(r.tool_calls_count for r in cat_results) / cat_total, 1),
        }

    return AgentEvalMetrics(
        mode=mode,
        total=total,
        successful=successful,
        failed=failed,
        success_rate=round(successful / total, 4),
        avg_duration_ms=round(avg_duration, 1),
        avg_iterations=round(avg_iters, 1),
        avg_tool_calls=round(avg_tools, 1),
        avg_retries=round(avg_retries, 1),
        avg_replans=round(avg_replans, 1),
        tool_accuracy=round(tool_accuracy, 4),
        partial_success=partial,
        recovery_rate=round(recovery_rate, 4),
        total_duration_ms=total_duration,
        per_category=per_category,
        failure_categories=failure_cats,
        error_counts=error_counts,
    )


def compute_delta(
    baseline: AgentEvalMetrics, veyron: AgentEvalMetrics
) -> dict[str, float | str]:
    return {
        "success_rate_delta": round(veyron.success_rate - baseline.success_rate, 4),
        "duration_delta_ms": round(veyron.avg_duration_ms - baseline.avg_duration_ms, 1),
        "iterations_delta": round(veyron.avg_iterations - baseline.avg_iterations, 1),
        "tool_calls_delta": round(veyron.avg_tool_calls - baseline.avg_tool_calls, 1),
        "retries_delta": round(veyron.avg_retries - baseline.avg_retries, 1),
        "replans_delta": round(veyron.avg_replans - baseline.avg_replans, 1),
        "tool_accuracy_delta": round(veyron.tool_accuracy - baseline.tool_accuracy, 4),
        "partial_success_delta": veyron.partial_success - baseline.partial_success,
        "recovery_rate_delta": round(veyron.recovery_rate - baseline.recovery_rate, 4),
    }


def _compute_tool_accuracy(results: list[EvalResult]) -> float:
    scored = 0
    matches = 0
    for r in results:
        expected = r.details.get("expected_tools", [])
        if not expected:
            continue
        scored += 1
        if r.tool_calls_count > 0:
            matches += 1
    return matches / scored if scored > 0 else 0.0
