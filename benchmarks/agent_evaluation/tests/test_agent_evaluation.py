from __future__ import annotations

from veyron.core.evaluator import EvalResult

from benchmarks.agent_evaluation.dataset import (
    ALL_TASKS,
    CATEGORY_MAP,
    BenchmarkTask,
    get_task_by_id,
    get_tasks_by_category,
    summary,
)
from benchmarks.agent_evaluation.metrics import (
    AgentEvalMetrics,
    compute_delta,
    compute_metrics,
)
from benchmarks.agent_evaluation.report import format_comparison, format_summary


class TestDataset:
    def test_total_tasks_at_least_100(self):
        assert len(ALL_TASKS) >= 100

    def test_all_categories_present(self):
        cats = {t.task.category for t in ALL_TASKS}
        for expected in CATEGORY_MAP.values():
            assert expected in cats, f"missing category: {expected}"

    def test_each_task_has_unique_id(self):
        ids = [t.task.id for t in ALL_TASKS]
        assert len(ids) == len(set(ids))

    def test_each_task_has_prompt(self):
        for t in ALL_TASKS:
            assert t.task.prompt, f"task {t.task.id} has empty prompt"

    def test_get_tasks_by_category(self):
        fs_tasks = get_tasks_by_category("filesystem")
        assert len(fs_tasks) > 0
        for t in fs_tasks:
            assert t.task.category == "filesystem"

    def test_get_tasks_by_category_none(self):
        assert len(get_tasks_by_category()) == len(ALL_TASKS)

    def test_get_task_by_id(self):
        t = get_task_by_id("fs_ls")
        assert t is not None
        assert t.task.id == "fs_ls"

    def test_get_task_by_id_missing(self):
        assert get_task_by_id("nonexistent") is None

    def test_summary(self):
        s = summary()
        assert s["total"] == len(ALL_TASKS)
        assert len(s["by_category"]) == len(CATEGORY_MAP)
        assert sum(s["by_category"].values()) == len(ALL_TASKS)

    def test_benchmark_task_dataclass(self):
        task = BenchmarkTask(
            task=EvalResult(task_id="test", category="test", prompt="test", success=True, duration_ms=0, iterations=0, tool_calls_count=0, retry_count=0),
            difficulty="advanced",
            expected_behavior="recovery",
        )


class TestMetrics:
    def test_compute_metrics_empty(self):
        metrics = compute_metrics([], "baseline")
        assert metrics.total == 0
        assert metrics.success_rate == 0.0

    def test_compute_metrics_all_pass(self):
        results = [
            EvalResult(task_id="t1", category="filesystem", prompt="test", success=True, duration_ms=100, iterations=2, tool_calls_count=1, retry_count=0, replan_count=0),
            EvalResult(task_id="t2", category="system_monitor", prompt="test", success=True, duration_ms=200, iterations=3, tool_calls_count=2, retry_count=1, replan_count=0),
        ]
        metrics = compute_metrics(results, "baseline")
        assert metrics.total == 2
        assert metrics.successful == 2
        assert metrics.success_rate == 1.0
        assert metrics.avg_duration_ms == 150.0
        assert metrics.avg_iterations == 2.5
        assert metrics.avg_tool_calls == 1.5
        assert metrics.avg_retries == 0.5

    def test_compute_metrics_mixed(self):
        results = [
            EvalResult(task_id="t1", category="filesystem", prompt="test", success=True, duration_ms=100, iterations=2, tool_calls_count=1, retry_count=0, replan_count=0, details={"expected_tools": ["fs"], "expected_behavior": "success"}),
            EvalResult(task_id="t2", category="terminal", prompt="test", success=False, duration_ms=50, iterations=1, tool_calls_count=1, retry_count=0, replan_count=0, error="timeout reading file", details={"expected_tools": ["term"], "expected_behavior": "success"}),
            EvalResult(task_id="t3", category="multi_step", prompt="test", success=False, duration_ms=300, iterations=4, tool_calls_count=0, retry_count=2, replan_count=1, error="exception: something broke", details={"expected_tools": ["fs", "sys"], "expected_behavior": "recovery"}),
        ]
        metrics = compute_metrics(results, "veyron")
        assert metrics.total == 3
        assert metrics.successful == 1
        assert metrics.failed == 2
        assert abs(metrics.success_rate - 1/3) < 0.001
        assert metrics.partial_success == 1
        assert metrics.failure_categories.get("timeout") == 1
        assert metrics.failure_categories.get("exception") == 1

    def test_tool_accuracy(self):
        results = [
            EvalResult(task_id="t1", category="test", prompt="test", success=True, duration_ms=0, iterations=1, tool_calls_count=2, retry_count=0, details={"expected_tools": ["ls", "cpu"]}),
            EvalResult(task_id="t2", category="test", prompt="test", success=False, duration_ms=0, iterations=1, tool_calls_count=0, retry_count=0, details={"expected_tools": ["mem"]}),
        ]
        metrics = compute_metrics(results, "baseline")
        assert metrics.tool_accuracy == 0.5

    def test_per_category_breakdown(self):
        results = [
            EvalResult(task_id="t1", category="filesystem", prompt="test", success=True, duration_ms=100, iterations=2, tool_calls_count=1, retry_count=0, replan_count=0),
            EvalResult(task_id="t2", category="filesystem", prompt="test", success=False, duration_ms=50, iterations=1, tool_calls_count=1, retry_count=0, replan_count=0, error="error"),
            EvalResult(task_id="t3", category="terminal", prompt="test", success=True, duration_ms=200, iterations=3, tool_calls_count=2, retry_count=1, replan_count=0),
        ]
        metrics = compute_metrics(results, "baseline")
        assert "filesystem" in metrics.per_category
        assert "terminal" in metrics.per_category
        assert metrics.per_category["filesystem"]["passed"] == 1
        assert metrics.per_category["filesystem"]["failed"] == 1
        assert metrics.per_category["filesystem"]["pass_rate"] == 0.5
        assert metrics.per_category["terminal"]["passed"] == 1
        assert metrics.per_category["terminal"]["pass_rate"] == 1.0

    def test_compute_delta(self):
        baseline = AgentEvalMetrics(mode="baseline", total=10, successful=7, success_rate=0.7, avg_duration_ms=100.0, avg_iterations=3.0, avg_tool_calls=2.0, avg_retries=0.5, tool_accuracy=0.6, recovery_rate=0.5)
        veyron = AgentEvalMetrics(mode="veyron", total=10, successful=9, success_rate=0.9, avg_duration_ms=120.0, avg_iterations=3.5, avg_tool_calls=2.0, avg_retries=0.3, tool_accuracy=0.8, recovery_rate=0.8)
        delta = compute_delta(baseline, veyron)
        assert delta["success_rate_delta"] == 0.2
        assert delta["duration_delta_ms"] == 20.0
        assert delta["retries_delta"] == -0.2
        assert delta["tool_accuracy_delta"] == 0.2
        assert delta["recovery_rate_delta"] == 0.3


class TestReport:
    def test_format_summary_includes_both_modes(self):
        baseline = AgentEvalMetrics(mode="baseline", total=10, successful=7, success_rate=0.7, avg_duration_ms=100.0, avg_iterations=3.0, avg_tool_calls=2.0, avg_retries=0.5, tool_accuracy=0.6, recovery_rate=0.5)
        veyron = AgentEvalMetrics(mode="veyron", total=10, successful=9, success_rate=0.9, avg_duration_ms=120.0, avg_iterations=3.5, avg_tool_calls=2.0, avg_retries=0.3, tool_accuracy=0.8, recovery_rate=0.8)
        output = format_summary(baseline, veyron)
        assert "BASELINE" in output
        assert "VEYRON" in output
        assert "70.0%" in output
        assert "90.0%" in output

    def test_format_comparison_includes_delta(self):
        baseline = AgentEvalMetrics(mode="baseline", total=10, successful=7, success_rate=0.7, avg_duration_ms=100.0, avg_iterations=3.0, avg_tool_calls=2.0, avg_retries=0.5, tool_accuracy=0.6, recovery_rate=0.5)
        veyron = AgentEvalMetrics(mode="veyron", total=10, successful=9, success_rate=0.9, avg_duration_ms=120.0, avg_iterations=3.5, avg_tool_calls=2.0, avg_retries=0.3, tool_accuracy=0.8, recovery_rate=0.8)

        fake_comparison = type("FakeComparison", (), {
            "baseline": baseline,
            "veyron": veyron,
            "delta": {
                "success_rate_delta": 0.2,
                "duration_delta_ms": 20.0,
                "iterations_delta": 0.5,
                "tool_calls_delta": 0.0,
                "retries_delta": -0.2,
                "replans_delta": 0.0,
                "tool_accuracy_delta": 0.2,
                "partial_success_delta": 0,
                "recovery_rate_delta": 0.3,
            },
        })

        output = format_comparison(fake_comparison)
        assert "IMPROVEMENTS" in output
        assert "Success Rate" in output
        assert "+0.20pp" in output or "+0.20" in output
