from __future__ import annotations

from benchmarks.agent_evaluation.metrics import AgentEvalMetrics


def _bar(val: float, width: int = 20) -> str:
    filled = int(val * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def format_summary(baseline: AgentEvalMetrics, veyron: AgentEvalMetrics) -> str:
    lines = [
        "=" * 70,
        "AGENT EVALUATION — BASELINE vs VEYRON",
        "=" * 70,
        "",
        f"  {'':20s} {'BASELINE':>12s} {'VEYRON':>12s} {'DELTA':>12s}",
        f"  {'─'*20} {'─'*12} {'─'*12} {'─'*12}",
        "",
    ]

    rows = [
        ("Total tasks", f"{baseline.total}", f"{veyron.total}", ""),
        ("Passed", f"{baseline.successful}", f"{veyron.successful}", f"{veyron.successful - baseline.successful:+d}"),
        ("Failed", f"{baseline.failed}", f"{veyron.failed}", f"{veyron.failed - baseline.failed:+d}"),
        ("Success rate", f"{baseline.success_rate*100:.1f}%", f"{veyron.success_rate*100:.1f}%", f"{(veyron.success_rate - baseline.success_rate)*100:+.1f}pp"),
        ("Partial success", f"{baseline.partial_success}", f"{veyron.partial_success}", f"{veyron.partial_success - baseline.partial_success:+d}"),
        ("",
        "",
        "",
        ""),
        ("Avg duration (ms)",
        f"{baseline.avg_duration_ms:.0f}",
        f"{veyron.avg_duration_ms:.0f}",
        f"{veyron.avg_duration_ms - baseline.avg_duration_ms:+.0f}"),
        ("Avg iterations",
        f"{baseline.avg_iterations:.1f}",
        f"{veyron.avg_iterations:.1f}",
        f"{veyron.avg_iterations - baseline.avg_iterations:+.1f}"),
        ("Avg tool calls",
        f"{baseline.avg_tool_calls:.1f}",
        f"{veyron.avg_tool_calls:.1f}",
        f"{veyron.avg_tool_calls - baseline.avg_tool_calls:+.1f}"),
        ("Avg retries",
        f"{baseline.avg_retries:.2f}",
        f"{veyron.avg_retries:.2f}",
        f"{veyron.avg_retries - baseline.avg_retries:+.2f}"),
        ("",
        "",
        "",
        ""),
        ("Tool accuracy",
        f"{baseline.tool_accuracy*100:.1f}%",
        f"{veyron.tool_accuracy*100:.1f}%",
        f"{(veyron.tool_accuracy - baseline.tool_accuracy)*100:+.1f}pp"),
        ("Recovery rate",
        f"{baseline.recovery_rate*100:.1f}%",
        f"{veyron.recovery_rate*100:.1f}%",
        f"{(veyron.recovery_rate - baseline.recovery_rate)*100:+.1f}pp"),
    ]

    for label, b, p, d in rows:
        if label:
            lines.append(f"  {label:25s} {b:>10s}  {p:>10s}  {d:>12s}")
        else:
            lines.append("")

    lines += [
        "",
        "─" * 70,
    ]

    all_categories = sorted(set(baseline.per_category.keys()) | set(veyron.per_category.keys()))
    if all_categories:
        lines.append("")
        lines.append("  PER-CATEGORY BREAKDOWN")
        lines.append("")
        lines.append(f"  {'Category':22s} {'BASELINE':>18s} {'VEYRON':>18s}")
        lines.append(f"  {'─'*22} {'─'*18} {'─'*18}")
        for cat in all_categories:
            b_cat = baseline.per_category.get(cat, {})
            p_cat = veyron.per_category.get(cat, {})
            b_rate = b_cat.get("pass_rate", 0.0) * 100
            p_rate = p_cat.get("pass_rate", 0.0) * 100
            b_dur = b_cat.get("avg_duration_ms", 0)
            p_dur = p_cat.get("avg_duration_ms", 0)
            b_str = f"{b_cat.get('passed', 0)}/{b_cat.get('total', 0)} ({b_rate:.0f}%) {b_dur:.0f}ms"
            p_str = f"{p_cat.get('passed', 0)}/{p_cat.get('total', 0)} ({p_rate:.0f}%) {p_dur:.0f}ms"
            lines.append(f"  {cat:22s} {b_str:>18s} {p_str:>18s}")

    lines += [
        "",
        "─" * 70,
    ]

    return "\n".join(lines)


def format_comparison(comparison) -> str:
    lines = [
        "=" * 70,
        "COMPARISON DELTA",
        "=" * 70,
    ]

    delta = comparison.delta
    improvements = []
    regressions = []
    neutrals = []

    for key, val in delta.items():
        if isinstance(val, (int, float)):
            if val > 0:
                label = key.replace("_delta", "").replace("_", " ").title()
                improvements.append((label, val))
            elif val < 0:
                label = key.replace("_delta", "").replace("_", " ").title()
                regressions.append((label, val))
            else:
                label = key.replace("_delta", "").replace("_", " ").title()
                neutrals.append((label, val))

    if improvements:
        lines.append("")
        lines.append("  ✅ IMPROVEMENTS")
        for label, val in improvements:
            suffix = "pp" if "rate" in label.lower() or "accuracy" in label.lower() else ""
            lines.append(f"    {label:25s} {val:+.2f}{suffix}")

    if regressions:
        lines.append("")
        lines.append("  ⚠ REGRESSIONS")
        for label, val in regressions:
            lines.append(f"    {label:25s} {val:+.2f}")

    if neutrals:
        lines.append("")
        lines.append("  ➡ UNCHANGED")
        for label, val in neutrals:
            lines.append(f"    {label:25s} {val:+.2f}")

    lines += [
        "",
        "=" * 70,
    ]

    return "\n".join(lines)


def format_task_details(result, task: object) -> str:
    from benchmarks.agent_evaluation.dataset import BenchmarkTask

    if not isinstance(task, BenchmarkTask):
        return ""
    lines = [
        f"  Task: {task.task.id} ({task.difficulty})",
        f"    Prompt: {task.task.prompt[:80]}...",
        f"    Expected tools: {task.task.expected_tools}",
        f"    Result: {'PASS' if result.success else 'FAIL'}",
        f"    Duration: {result.duration_ms}ms",
        f"    Iterations: {result.iterations}",
        f"    Tool calls: {result.tool_calls_count}",
    ]
    if result.error:
        lines.append(f"    Error: {result.error[:100]}")
    return "\n".join(lines)
