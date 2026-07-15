"""Tests for Phase 9.3: evaluation, trainer_v2, and benchmark_v2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from veyron.intelligence.intent.model import IntentModel
from veyron.intelligence.tool_selector.model import ToolSelectorModel
from veyron.intelligence.training.dataset import TrainingDataset, TrainingExample
from veyron.intelligence.training.evaluation import (
    IntentEvalReport,
    IntentEvaluator,
    ModelComparison,
    ToolSelectorEvalReport,
    ToolSelectorEvaluator,
)
from veyron.intelligence.training.trainer_v2 import TrainingPipelineV2

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mini_dataset() -> TrainingDataset:
    examples = [
        TrainingExample(request="show cpu usage now", intent="system_management", tools_used=["system_monitor"]),
        TrainingExample(request="check memory usage", intent="system_management", tools_used=["system_monitor"]),
        TrainingExample(request="read the readme file", intent="file_operation", tools_used=["filesystem_read"]),
        TrainingExample(request="list directory contents", intent="file_operation", tools_used=["filesystem_read"]),
        TrainingExample(request="analyze project structure", intent="project_analysis", tools_used=["project_analyzer"]),
        TrainingExample(request="run npm install command", intent="tool_execution", tools_used=["terminal"]),
        TrainingExample(request="debug the build failure", intent="debugging", tools_used=["terminal", "filesystem_read"]),
        TrainingExample(request="fix the crash error", intent="debugging", tools_used=["terminal"]),
        TrainingExample(request="hello how are you", intent="conversation", tools_used=[]),
        TrainingExample(request="good morning", intent="conversation", tools_used=[]),
        TrainingExample(request="what is the weather today", intent="question_answering", tools_used=[]),
        TrainingExample(request="write a sorting algorithm", intent="coding_task", tools_used=["filesystem_read"]),
        TrainingExample(request="plan the deployment steps", intent="planning_task", tools_used=["terminal", "filesystem_read"]),
        TrainingExample(request="research quantum computing", intent="research", tools_used=["filesystem_read"]),
    ]
    return TrainingDataset(examples)


@pytest.fixture
def trained_intent_model(mini_dataset: TrainingDataset) -> IntentModel:
    pipeline = TrainingPipelineV2()
    model, _ = pipeline.train_intent(mini_dataset)
    return model


@pytest.fixture
def trained_ts_model(mini_dataset: TrainingDataset) -> ToolSelectorModel:
    pipeline = TrainingPipelineV2()
    model, _ = pipeline.train_tool_selector(mini_dataset)
    return model


# ── IntentEvaluator tests ─────────────────────────────────────────────────────

def test_intent_evaluator_accuracy(trained_intent_model: IntentModel, mini_dataset: TrainingDataset):
    texts = [ex.request for ex in mini_dataset.examples]
    labels = [ex.intent for ex in mini_dataset.examples]
    report = IntentEvaluator().evaluate(trained_intent_model, texts, labels)
    assert report.total == 14
    assert 0 <= report.accuracy <= 1.0
    assert report.correct + (report.total - report.correct) == report.total


def test_intent_evaluator_per_category(trained_intent_model: IntentModel, mini_dataset: TrainingDataset):
    texts = [ex.request for ex in mini_dataset.examples]
    labels = [ex.intent for ex in mini_dataset.examples]
    report = IntentEvaluator().evaluate(trained_intent_model, texts, labels)
    assert len(report.per_category) >= 5
    for cat, metrics in report.per_category.items():
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1_score" in metrics
        assert "support" in metrics


def test_intent_evaluator_report_to_dict(trained_intent_model: IntentModel, mini_dataset: TrainingDataset):
    texts = [ex.request for ex in mini_dataset.examples]
    labels = [ex.intent for ex in mini_dataset.examples]
    report = IntentEvaluator().evaluate(trained_intent_model, texts, labels)
    d = report.to_dict()
    assert "accuracy" in d
    assert "per_category" in d
    assert "calibration" in d
    assert "confusion_matrix" in d
    assert "common_mistakes" in d
    assert "weak_categories" in d


def test_intent_evaluator_empty():
    model = IntentModel()
    model.fit(["hello", "world"], ["conversation", "system_management"])
    report = IntentEvaluator().evaluate(model, [], [])
    assert report.total == 0
    assert report.accuracy == 0.0


def test_intent_evaluator_calibration(trained_intent_model: IntentModel, mini_dataset: TrainingDataset):
    texts = [ex.request for ex in mini_dataset.examples]
    labels = [ex.intent for ex in mini_dataset.examples]
    report = IntentEvaluator().evaluate(trained_intent_model, texts, labels)
    assert len(report.calibration) >= 1
    for bucket in report.calibration:
        assert "bucket" in bucket
        assert "count" in bucket
        assert "avg_confidence" in bucket
        assert "accuracy" in bucket


def test_intent_evaluator_confusion_matrix(trained_intent_model: IntentModel, mini_dataset: TrainingDataset):
    texts = [ex.request for ex in mini_dataset.examples]
    labels = [ex.intent for ex in mini_dataset.examples]
    report = IntentEvaluator().evaluate(trained_intent_model, texts, labels)
    assert len(report.confusion_matrix) >= 5
    for cat, row in report.confusion_matrix.items():
        assert isinstance(row, dict)
        assert sum(row.values()) == sum(1 for l in labels if l == cat)


# ── ToolSelectorEvaluator tests ───────────────────────────────────────────────

def test_ts_evaluator_metrics(trained_ts_model: ToolSelectorModel, mini_dataset: TrainingDataset):
    texts = [ex.request for ex in mini_dataset.examples]
    targets = [ex.tools_used for ex in mini_dataset.examples]
    report = ToolSelectorEvaluator().evaluate(trained_ts_model, texts, targets)
    assert report.total_examples == 14
    assert 0 <= report.precision_at_1 <= 1.0
    assert 0 <= report.recall_at_3 <= 1.0


def test_ts_evaluator_per_tool(trained_ts_model: ToolSelectorModel, mini_dataset: TrainingDataset):
    texts = [ex.request for ex in mini_dataset.examples]
    targets = [ex.tools_used for ex in mini_dataset.examples]
    report = ToolSelectorEvaluator().evaluate(trained_ts_model, texts, targets)
    assert len(report.per_tool) >= 2
    for tool, metrics in report.per_tool.items():
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1" in metrics


def test_ts_evaluator_report_to_dict(trained_ts_model: ToolSelectorModel, mini_dataset: TrainingDataset):
    texts = [ex.request for ex in mini_dataset.examples]
    targets = [ex.tools_used for ex in mini_dataset.examples]
    report = ToolSelectorEvaluator().evaluate(trained_ts_model, texts, targets)
    d = report.to_dict()
    assert "precision@1" in d
    assert "precision@3" in d
    assert "recall@1" in d
    assert "recall@3" in d
    assert "per_tool" in d
    assert "calibration" in d


def test_ts_evaluator_empty():
    model = ToolSelectorModel()
    model.fit(["hello"], [["terminal"]])
    report = ToolSelectorEvaluator().evaluate(model, [], [])
    assert report.total_examples == 0
    assert report.precision_at_1 == 0.0


# ── ModelComparison tests ─────────────────────────────────────────────────────

def test_model_comparison_intent(trained_intent_model: IntentModel, mini_dataset: TrainingDataset):
    model_a = trained_intent_model
    model_b = IntentModel()
    model_b.fit(
        [ex.request for ex in mini_dataset.examples],
        [ex.intent for ex in mini_dataset.examples],
    )
    texts = [ex.request for ex in mini_dataset.examples]
    labels = [ex.intent for ex in mini_dataset.examples]
    result = ModelComparison().compare_intent_models(model_a, model_b, texts, labels)
    assert "model_a" in result
    assert "model_b" in result
    assert "delta" in result
    assert "accuracy" in result["delta"]
    assert "macro_f1" in result["delta"]


def test_model_comparison_ts(trained_ts_model: ToolSelectorModel, mini_dataset: TrainingDataset):
    texts = [ex.request for ex in mini_dataset.examples]
    targets = [ex.tools_used for ex in mini_dataset.examples]
    result = ModelComparison().compare_tool_selector_models(
        trained_ts_model, trained_ts_model, texts, targets,
    )
    assert "model_a" in result
    assert "model_b" in result
    assert "delta" in result
    assert result["delta"]["precision@1"] == 0.0


# ── TrainingPipelineV2 tests ──────────────────────────────────────────────────

def test_train_intent_returns_model_and_report(mini_dataset: TrainingDataset):
    pipeline = TrainingPipelineV2()
    model, report = pipeline.train_intent(mini_dataset)
    assert isinstance(model, IntentModel)
    assert model.fitted
    assert isinstance(report, IntentEvalReport)
    assert report.total > 0


def test_train_tool_selector_returns_model_and_report(mini_dataset: TrainingDataset):
    pipeline = TrainingPipelineV2()
    model, report = pipeline.train_tool_selector(mini_dataset)
    assert isinstance(model, ToolSelectorModel)
    assert model.fitted
    assert isinstance(report, ToolSelectorEvalReport)
    assert report.total_examples > 0


def test_train_all_returns_both(mini_dataset: TrainingDataset):
    pipeline = TrainingPipelineV2()
    result = pipeline.train_all(mini_dataset)
    assert "intent_model" in result
    assert "tool_selector_model" in result
    assert "intent_report" in result
    assert "tool_selector_report" in result


def test_train_with_explicit_test_set(mini_dataset: TrainingDataset):
    splitter = __import__("veyron.intelligence.training.preparation.splitter", fromlist=["DatasetSplitter"]).DatasetSplitter()
    train, test = splitter.stratified_split(mini_dataset, seed=42)
    pipeline = TrainingPipelineV2()
    model, report = pipeline.train_intent(train, test_dataset=test)
    assert model.fitted
    assert report.total > 0


def test_save_models_creates_files(mini_dataset: TrainingDataset, tmp_path: Path):
    pipeline = TrainingPipelineV2(output_dir=tmp_path)
    model, _ = pipeline.train_intent(mini_dataset)
    saved = pipeline.save_models(intent_model=model, output_dir=tmp_path)
    assert "intent_model" in saved
    assert saved["intent_model"].exists()


def test_save_models_creates_latest_copy(mini_dataset: TrainingDataset, tmp_path: Path):
    pipeline = TrainingPipelineV2(output_dir=tmp_path)
    model, _ = pipeline.train_intent(mini_dataset)
    pipeline.save_models(intent_model=model, output_dir=tmp_path)
    latest = tmp_path / "intent_classifier.pkl"
    assert latest.exists()


def test_save_reports_creates_files(mini_dataset: TrainingDataset, tmp_path: Path):
    pipeline = TrainingPipelineV2(output_dir=tmp_path)
    _, report = pipeline.train_intent(mini_dataset)
    saved = pipeline.save_reports(intent_report=report, output_dir=tmp_path)
    assert "intent_report" in saved
    assert saved["intent_report"].exists()
    with open(saved["intent_report"], encoding="utf-8") as f:
        data = json.load(f)
    assert "accuracy" in data


def test_save_reports_ts(mini_dataset: TrainingDataset, tmp_path: Path):
    pipeline = TrainingPipelineV2(output_dir=tmp_path)
    _, report = pipeline.train_tool_selector(mini_dataset)
    saved = pipeline.save_reports(ts_report=report, output_dir=tmp_path)
    assert "tool_selector_report" in saved
    with open(saved["tool_selector_report"], encoding="utf-8") as f:
        data = json.load(f)
    assert "precision@1" in data


def test_train_intent_uses_seed_for_reproducibility(mini_dataset: TrainingDataset):
    pipeline = TrainingPipelineV2()
    model1, _ = pipeline.train_intent(mini_dataset, seed=42)
    model2, _ = pipeline.train_intent(mini_dataset, seed=42)
    t1 = model1.predict("show cpu")
    t2 = model2.predict("show cpu")
    assert t1 == t2


def test_train_tool_selector_with_different_tools():
    examples = [
        TrainingExample(request="read file", intent="file_operation", tools_used=["filesystem_read"]),
        TrainingExample(request="list directory", intent="file_operation", tools_used=["filesystem_read"]),
        TrainingExample(request="monitor system", intent="system_management", tools_used=["system_monitor"]),
        TrainingExample(request="check cpu usage", intent="system_management", tools_used=["system_monitor"]),
        TrainingExample(request="run command", intent="tool_execution", tools_used=["terminal"]),
        TrainingExample(request="execute script", intent="tool_execution", tools_used=["terminal"]),
    ]
    dataset = TrainingDataset(examples)
    pipeline = TrainingPipelineV2()
    model, report = pipeline.train_tool_selector(dataset)
    assert model.fitted
    assert len(model.tool_names) >= 3


# ── Dataclass tests ───────────────────────────────────────────────────────────

def test_intent_eval_report_defaults():
    r = IntentEvalReport()
    assert r.accuracy == 0.0
    assert r.correct == 0
    assert r.total == 0
    d = r.to_dict()
    assert d["accuracy"] == 0.0


def test_tool_selector_eval_report_defaults():
    r = ToolSelectorEvalReport()
    assert r.precision_at_1 == 0.0
    assert r.total_examples == 0
    d = r.to_dict()
    assert d["precision@1"] == 0.0
