"""Tests for the Phase 11.5 Intelligence Benchmark.

Covers:
  - Dataset loading
  - Parameter extraction evaluator (enhanced)
  - Tool selection benchmark (micro-model and baseline modes)
  - Intent classification benchmark
  - Latency measurement
  - Regression detection
  - Full comparison flow
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from veyron.intelligence.parameter_extraction.evaluation import ParameterExtractionEvaluator
from veyron.intelligence.parameter_extraction.model import ParameterExtractionModel
from veyron.intelligence.tool_selector.model import ToolSelectorModel

from benchmarks.intelligence_benchmark import (
    BenchmarkConfig,
    _detect_regressions,
    _domain_to_expected_tools,
    _heuristic_intent_from_domain,
    _run_intent_benchmark,
    _run_latency_benchmark,
    _run_param_extraction_benchmark,
    _run_tool_selection_benchmark,
    load_dataset,
    run_benchmark,
    run_mode,
)

# ═══════════════════════════════════════════════════════════════════
# Dataset loading
# ═══════════════════════════════════════════════════════════════════


class TestDatasetLoading:
    def test_load_default_dataset(self):
        """The curated benchmark JSON must load successfully."""
        data = load_dataset(Path(__file__).parents[2] / "benchmarks" / "datasets" / "intelligence_benchmark.json")
        assert "metadata" in data
        assert data["metadata"]["version"] == "1.0"
        assert len(data.get("param_extraction", [])) > 0
        assert len(data.get("tool_selection", [])) > 0
        assert len(data.get("task_success", [])) > 0
        assert len(data.get("regression", [])) > 0

    def test_load_missing_dataset_raises(self):
        with pytest.raises(FileNotFoundError):
            load_dataset("/nonexistent/path.json")

    def test_inline_tiny_dataset(self, tmp_path):
        """A tiny inline dataset must be usable by the benchmark."""
        data = {
            "metadata": {"version": "1.0"},
            "param_extraction": [
                {"id": "p1", "request": "list files", "tool_name": "filesystem_read",
                 "expected_parameters": {"path": "."}},
            ],
            "tool_selection": [
                {"id": "t1", "request": "check cpu", "expected_tools": ["system_monitor"]},
            ],
            "task_success": [],
            "regression": [],
        }
        path = tmp_path / "tiny.json"
        with open(path, "w") as f:
            json.dump(data, f)
        loaded = load_dataset(path)
        assert len(loaded["param_extraction"]) == 1
        assert len(loaded["tool_selection"]) == 1


# ═══════════════════════════════════════════════════════════════════
# Parameter extraction evaluator
# ═══════════════════════════════════════════════════════════════════


class TestParameterExtractionEvaluator:
    def test_evaluate_model_exact_match(self):
        model = ParameterExtractionModel()
        model.fit([
            ("list files in tests", "filesystem_read", {"path": "tests"}),
            ("check cpu", "system_monitor", {"metric": "cpu"}),
        ])
        test_cases = [
            {"id": "t1", "request": "list files in tests", "tool_name": "filesystem_read",
             "expected_parameters": {"path": "tests"}},
            {"id": "t2", "request": "check cpu", "tool_name": "system_monitor",
             "expected_parameters": {"metric": "cpu"}},
        ]
        evaluator = ParameterExtractionEvaluator()
        metrics = evaluator.evaluate_model(model, test_cases)
        assert metrics["total"] == 2
        assert metrics["exact_match_rate"] == 1.0

    def test_evaluate_model_partial_match(self):
        model = ParameterExtractionModel()
        model.fit([
            ("list files in tests", "filesystem_read", {"path": "tests", "pattern": "*.py"}),
            ("list files in src", "filesystem_read", {"path": "src", "pattern": "*.ts"}),
        ])
        # Request similar to training but parameter differs slightly.
        test_cases = [
            {"id": "t1", "request": "list files in tests", "tool_name": "filesystem_read",
             "expected_parameters": {"path": "tests", "pattern": "*.py"}},
        ]
        evaluator = ParameterExtractionEvaluator()
        metrics = evaluator.evaluate_model(model, test_cases)
        assert metrics["total"] == 1
        assert len(metrics["per_tool"]) > 0

    def test_evaluate_model_no_model_returns_available_false(self):
        metrics = _run_param_extraction_benchmark([], model=None)
        assert metrics["available"] is False

    def test_evaluate_model_tiny(self):
        """Verify per-tool breakdown exists."""
        model = ParameterExtractionModel()
        model.fit([
            ("list tests", "filesystem_read", {"path": "tests"}),
            ("check cpu", "system_monitor", {"metric": "cpu"}),
        ])
        test_cases = [
            {"id": "t1", "request": "list tests", "tool_name": "filesystem_read",
             "expected_parameters": {"path": "tests"}},
        ]
        evaluator = ParameterExtractionEvaluator()
        metrics = evaluator.evaluate_model(model, test_cases)
        assert "per_tool" in metrics
        assert "filesystem_read" in metrics["per_tool"]


# ═══════════════════════════════════════════════════════════════════
# Tool selection benchmark
# ═══════════════════════════════════════════════════════════════════


class TestToolSelectionBenchmark:
    def test_micro_model_mode(self):
        """Tool selection with a trained model."""
        model = ToolSelectorModel()
        model.fit(
            ["check cpu", "show memory", "list files", "read readme"],
            [["system_monitor"], ["system_monitor"], ["filesystem_read"], ["filesystem_read"]],
        )
        test_cases = [
            {"id": "t1", "request": "check cpu", "expected_tools": ["system_monitor"]},
            {"id": "t2", "request": "list files", "expected_tools": ["filesystem_read"]},
        ]
        metrics = _run_tool_selection_benchmark(test_cases, model, mode="micro_model")
        assert metrics["total"] == 2
        assert metrics["accuracy"] >= 0.0

    def test_baseline_mode(self):
        """Tool selection with heuristic domain mapping."""
        test_cases = [
            {"id": "t1", "request": "check cpu usage", "expected_tools": ["system_monitor"]},
            {"id": "t2", "request": "list files in directory", "expected_tools": ["filesystem_read"]},
        ]
        metrics = _run_tool_selection_benchmark(test_cases, tool_selector=None, mode="baseline")
        assert metrics["total"] == 2
        assert metrics["accuracy"] >= 0.0

    def test_empty_case_list(self):
        metrics = _run_tool_selection_benchmark([], tool_selector=None, mode="baseline")
        assert metrics["total"] == 0


# ═══════════════════════════════════════════════════════════════════
# Intent classification benchmark
# ═══════════════════════════════════════════════════════════════════


class TestIntentBenchmark:
    def test_micro_model_mode(self):
        test_cases = [
            {"id": "t1", "request": "check cpu usage", "expected_tools": ["system_monitor"]},
            {"id": "t2", "request": "hello", "expected_tools": []},
        ]
        metrics = _run_intent_benchmark(test_cases, mode="micro_model")
        assert metrics["total"] == 2
        assert metrics["accuracy"] >= 0.0
        assert metrics["avg_confidence"] > 0

    def test_baseline_mode(self):
        test_cases = [
            {"id": "t1", "request": "check cpu usage", "expected_tools": ["system_monitor"]},
        ]
        metrics = _run_intent_benchmark(test_cases, mode="baseline")
        assert metrics["total"] == 1

    def test_empty_case_list(self):
        metrics = _run_intent_benchmark([], mode="baseline")
        assert metrics["total"] == 0


# ═══════════════════════════════════════════════════════════════════
# Latency benchmark
# ═══════════════════════════════════════════════════════════════════


class TestLatencyBenchmark:
    def test_micro_model_mode(self):
        model = ParameterExtractionModel()
        model.fit([("list tests", "filesystem_read", {"path": "tests"})])
        tool_selector = ToolSelectorModel()
        tool_selector.fit(["check cpu"], [["system_monitor"]])
        test_cases = [
            {"id": "t1", "request": "check cpu usage", "expected_tools": ["system_monitor"]},
        ]
        metrics = _run_latency_benchmark(test_cases, model, tool_selector, mode="micro_model")
        assert "intent" in metrics
        assert "tool_selection" in metrics
        assert metrics["intent"]["samples"] > 0

    def test_baseline_mode(self):
        test_cases = [
            {"id": "t1", "request": "check cpu usage", "expected_tools": ["system_monitor"]},
        ]
        metrics = _run_latency_benchmark(test_cases, param_model=None, tool_selector=None, mode="baseline")
        assert "intent" in metrics
        assert metrics["intent"]["samples"] > 0
        # Tool selection and param extraction not measured in baseline.
        assert metrics["tool_selection"]["samples"] == 0
        assert metrics["parameter_extraction"]["samples"] == 0


# ═══════════════════════════════════════════════════════════════════
# Regression detection
# ═══════════════════════════════════════════════════════════════════


class TestRegressionDetection:
    def test_no_previous_report(self):
        result = _detect_regressions({"a": 1}, previous=None)
        assert result["found"] is False
        assert "No previous report" in result["note"]

    def test_no_regression(self):
        current = {
            "tool_selection": {"accuracy": 0.95, "avg_latency_ms": 1.0},
            "latency": {"intent": {"avg_ms": 0.5}},
        }
        previous = {
            "tool_selection": {"accuracy": 0.94, "avg_latency_ms": 1.0},
            "latency": {"intent": {"avg_ms": 0.5}},
        }
        result = _detect_regressions(current, previous)
        assert result["found"] is False

    def test_accuracy_regression(self):
        current = {"tool_selection": {"accuracy": 0.80}}
        previous = {"tool_selection": {"accuracy": 0.95}}
        result = _detect_regressions(current, previous)
        assert result["found"] is True
        assert result["count"] >= 1

    def test_latency_regression(self):
        current = {"latency": {"intent": {"avg_ms": 5.0}}}
        previous = {"latency": {"intent": {"avg_ms": 1.0}}}
        result = _detect_regressions(current, previous)
        assert result["found"] is True
        # 400% increase > 20% threshold.
        assert any("performance_regression" in str(i) for i in result["items"])


# ═══════════════════════════════════════════════════════════════════
# Full comparison flow
# ═══════════════════════════════════════════════════════════════════


class TestFullComparison:
    def test_run_benchmark_with_tiny_dataset(self, tmp_path):
        """End-to-end comparison with a tiny inline dataset and no real models."""
        data = {
            "metadata": {"version": "1.0"},
            "param_extraction": [
                {"id": "p1", "request": "list files", "tool_name": "filesystem_read",
                 "expected_parameters": {"path": "."}},
            ],
            "tool_selection": [
                {"id": "t1", "request": "check cpu", "expected_tools": ["system_monitor"]},
            ],
            "task_success": [],
            "regression": [
                {"id": "r1", "request": "hello", "type": "routing",
                 "expected_behavior": "conversation", "expected_tools": []},
            ],
        }
        dataset_path = tmp_path / "tiny_benchmark.json"
        with open(dataset_path, "w") as f:
            json.dump(data, f)

        config = BenchmarkConfig(
            dataset_path=dataset_path,
            output_dir=tmp_path / "output",
            skip_task_success=True,
        )
        report = run_benchmark(config)

        assert report.micro_model["mode"] == "micro_model"
        assert report.baseline["mode"] == "baseline"
        assert "param_extraction" in report.delta
        assert "tool_selection" in report.delta
        assert "latency" in report.delta
        assert len(report.delta) > 0

    def test_run_mode_micro_model(self, tmp_path):
        """Verify run_mode produces a ModeReport with expected sections."""
        data = {
            "metadata": {"version": "1.0"},
            "param_extraction": [],
            "tool_selection": [
                {"id": "t1", "request": "check cpu", "expected_tools": ["system_monitor"]},
            ],
            "task_success": [],
            "regression": [],
        }
        dataset_path = tmp_path / "tiny2.json"
        with open(dataset_path, "w") as f:
            json.dump(data, f)

        config = BenchmarkConfig(
            dataset_path=dataset_path,
            output_dir=tmp_path / "output2",
            skip_task_success=True,
        )
        report = run_mode(data, config, mode="micro_model")
        assert report.mode == "micro_model"
        assert report.tool_selection["total"] > 0
        assert report.param_extraction.get("total", 0) == 0
        # task_success has no cases, so it's not populated.
        assert report.task_success == {}


# ═══════════════════════════════════════════════════════════════════
# Heuristic helpers
# ═══════════════════════════════════════════════════════════════════


class TestHeuristicHelpers:
    def test_domain_to_expected_tools(self):
        assert "system_monitor" in _domain_to_expected_tools("system")
        assert "filesystem_read" in _domain_to_expected_tools("filesystem")
        assert "terminal" in _domain_to_expected_tools("terminal")
        assert "project_analyzer" in _domain_to_expected_tools("project")
        assert _domain_to_expected_tools("unknown") == []

    def test_heuristic_intent_from_domain(self):
        assert _heuristic_intent_from_domain("system") == "system_management"
        assert _heuristic_intent_from_domain("filesystem") == "file_operation"
        assert _heuristic_intent_from_domain("terminal") == "tool_execution"
        assert _heuristic_intent_from_domain("project") == "project_analysis"
        assert _heuristic_intent_from_domain("unknown") == "conversation"
