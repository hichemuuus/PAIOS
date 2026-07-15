"""Phase 14 tests — Real Intelligence Validation & Local LLM Integration.

Covers:
  - Enhanced TrainingDataset: merge, filter_by_source, source tracking
  - Enhanced UserInteraction: feedback_score, latency_breakdown
  - Enhanced quality scoring: recency_bonus, feedback_bonus
  - User feedback API endpoint
  - Benchmark comparison script orchestration
  - Provider diagnostics endpoint
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from veyron.intelligence.training.dataset import (
    TrainingDataset,
    TrainingExample,
    UserInteraction,
    load_user_interactions,
    save_user_interaction,
    user_interactions_to_dataset,
)
from veyron.intelligence.training.quality import QualityScorer

# ─── TrainingDataset enhancements ───────────────────────────────────────────


class TestTrainingDatasetEnhancements:
    def test_source_field_in_example(self):
        ex = TrainingExample(request="list files", intent="file_operation", source="user_interaction")
        assert ex.source == "user_interaction"
        d = ex.to_dict()
        assert d["source"] == "user_interaction"
        restored = TrainingExample.from_dict(d)
        assert restored.source == "user_interaction"

    def test_filter_by_source(self):
        ex1 = TrainingExample(request="a", intent="x", source="synthetic")
        ex2 = TrainingExample(request="b", intent="y", source="user_interaction")
        ex3 = TrainingExample(request="c", intent="z", source="synthetic")
        ds = TrainingDataset([ex1, ex2, ex3])
        syn = ds.filter_by_source("synthetic")
        assert len(syn) == 2
        real = ds.filter_by_source("user_interaction")
        assert len(real) == 1

    def test_merge_deduplicates(self):
        ex1 = TrainingExample(request="hello", intent="greeting", tools_used=["term"])
        ex2 = TrainingExample(request="hello", intent="greeting", tools_used=["term"])
        ex3 = TrainingExample(request="world", intent="greeting")
        ds1 = TrainingDataset([ex1])
        ds2 = TrainingDataset([ex2, ex3])
        merged = ds1.merge(ds2)
        assert len(merged) == 2

    def test_summary_includes_sources(self):
        ex1 = TrainingExample(request="a", intent="x", source="synthetic")
        ex2 = TrainingExample(request="b", intent="y", source="user_interaction")
        ds = TrainingDataset([ex1, ex2])
        s = ds.summary()
        assert "sources" in s
        assert s["sources"]["synthetic"] == 1
        assert s["sources"]["user_interaction"] == 1


# ─── UserInteraction enhancements ───────────────────────────────────────────


class TestUserInteractionEnhancements:
    def test_feedback_score_field(self):
        ui = UserInteraction(
            request="test", feedback_score=0.8,
            metadata={"duration_ms": 100, "total_steps": 2, "retry_count": 0, "tool_calls_count": 1},
        )
        assert ui.feedback_score == 0.8
        d = ui.to_dict()
        assert d["feedback_score"] == 0.8
        restored = UserInteraction.from_dict(d)
        assert restored.feedback_score == 0.8

    def test_feedback_score_none_by_default(self):
        ui = UserInteraction(request="test")
        assert ui.feedback_score is None

    def test_to_training_example_with_feedback(self):
        ui = UserInteraction(
            request="list files",
            detected_intent="file_operation",
            selected_tools=["fs"],
            quality_score=0.5,
            feedback_score=0.9,
            metadata={"duration_ms": 100, "total_steps": 2, "retry_count": 0, "tool_calls_count": 1},
        )
        ex = ui.to_training_example()
        assert ex.source == "user_interaction"
        assert ex.quality_score > 0.5
        assert ex.duration_ms == 100

    def test_to_training_example_without_feedback(self):
        ui = UserInteraction(
            request="list files",
            detected_intent="file_operation",
            quality_score=0.5,
            metadata={"duration_ms": 100, "total_steps": 2, "retry_count": 0, "tool_calls_count": 1},
        )
        ex = ui.to_training_example()
        assert ex.quality_score == 0.5

    def test_roundtrip_via_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            ui = UserInteraction(
                request="hello",
                detected_intent="greeting",
                feedback_score=0.75,
                metadata={"duration_ms": 50, "total_steps": 1, "retry_count": 0, "tool_calls_count": 1},
            )
            save_user_interaction(ui, directory=d)
            loaded = load_user_interactions(directory=d)
            assert len(loaded) == 1
            assert loaded[0].feedback_score == 0.75
            assert loaded[0].request == "hello"


# ─── Quality scoring enhancements ───────────────────────────────────────────


class TestQualityScorerEnhancements:
    def test_recency_bonus_recent(self):
        scorer = QualityScorer()
        recent_ts = datetime.now(UTC).isoformat()
        score = scorer.score({
            "success": True,
            "total_steps": 2,
            "retry_count": 0,
            "tools_used": ["fs"],
            "duration_ms": 100,
            "tool_calls_count": 1,
            "timestamp": recent_ts,
        })
        assert score.recency_bonus > 0.5

    def test_recency_bonus_old(self):
        scorer = QualityScorer()
        old_ts = "2020-01-01T00:00:00+00:00"
        score = scorer.score({
            "success": True,
            "total_steps": 2,
            "retry_count": 0,
            "tools_used": ["fs"],
            "duration_ms": 100,
            "tool_calls_count": 1,
            "timestamp": old_ts,
        })
        assert score.recency_bonus == 0.0

    def test_feedback_bonus(self):
        scorer = QualityScorer()
        score = scorer.score({
            "success": True,
            "total_steps": 2,
            "retry_count": 0,
            "tools_used": ["fs"],
            "duration_ms": 100,
            "tool_calls_count": 1,
            "feedback_score": 0.8,
        })
        assert score.feedback_bonus == pytest.approx(0.24, abs=0.01)

    def test_feedback_bonus_zero_when_missing(self):
        scorer = QualityScorer()
        score = scorer.score({
            "success": True,
            "total_steps": 2,
            "retry_count": 0,
            "tools_used": ["fs"],
            "duration_ms": 100,
            "tool_calls_count": 1,
        })
        assert score.feedback_bonus == 0.0


# ─── user_interactions_to_dataset with source ───────────────────────────────


class TestUserInteractionsToDataset:
    def test_source_in_converted_examples(self):
        with tempfile.TemporaryDirectory() as d:
            ui = UserInteraction(
                request="hello",
                detected_intent="greeting",
                quality_score=0.8,
                metadata={"duration_ms": 50, "total_steps": 1, "retry_count": 0, "tool_calls_count": 1},
            )
            save_user_interaction(ui, directory=d)

            dataset = user_interactions_to_dataset(directory=d)
            assert len(dataset) == 1
            assert dataset[0].source == "user_interaction"


# ─── Benchmark comparison helpers ───────────────────────────────────────────


class TestBenchmarkComparison:
    def test_print_comparison_format(self):
        from veyron.intelligence.training.benchmark_comparison import print_comparison

        results = {
            "datasets": {"synthetic": 100, "real": 20, "test": 30},
            "intent_classifier": [
                {"source": "synthetic", "dataset_size": 100, "accuracy": 0.85, "precision": 0.82, "recall": 0.80, "f1": 0.81, "latency_ms": 2.5, "per_category": {}},
                {"source": "real", "dataset_size": 20, "accuracy": 0.72, "precision": 0.70, "recall": 0.68, "f1": 0.69, "latency_ms": 2.1, "per_category": {}},
            ],
            "tool_selector": [
                {"source": "synthetic", "dataset_size": 100, "exact_match_rate": 0.75, "precision_at_1": 0.80, "recall_at_1": 0.78, "f1_at_3": 0.79, "latency_ms": 3.0, "per_tool": {}},
            ],
            "summary": {},
        }
        output = print_comparison(results)
        assert "synthetic" in output
        assert "real" in output
        assert "85.0%" in output
        assert "72.0%" in output

    def test_run_comparison_no_data(self):
        from veyron.intelligence.training.benchmark_comparison import run_comparison

        with patch("veyron.intelligence.training.benchmark_comparison._load_real_dataset", return_value=None), \
             patch("veyron.intelligence.training.benchmark_comparison._load_synthetic_dataset", return_value=None):
            results = run_comparison()
            assert "error" in results
