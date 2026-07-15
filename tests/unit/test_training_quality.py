"""Tests for TrainingDataCollector quality scoring."""

from __future__ import annotations

from veyron.intelligence.training.quality import QualityScorer


def test_perfect_example_scores_high():
    scorer = QualityScorer()
    example = {
        "success": True,
        "total_steps": 5,
        "retry_count": 0,
        "tools_used": ["filesystem_read", "system_monitor", "terminal"],
        "duration_ms": 3000,
        "tool_calls_count": 3,
    }
    score = scorer.score(example)
    assert score.overall >= 0.6
    assert score.completion_bonus == 1.0
    assert score.retry_penalty == 0.0
    assert score.recency_bonus == 0.0
    assert score.feedback_bonus == 0.0


def test_failed_example_scores_low():
    scorer = QualityScorer()
    example = {
        "success": False,
        "total_steps": 3,
        "retry_count": 2,
        "tools_used": [],
        "duration_ms": 5000,
        "tool_calls_count": 0,
    }
    score = scorer.score(example)
    assert score.overall < 0.5
    assert score.completion_bonus == 0.0


def test_high_retry_penalty():
    scorer = QualityScorer()
    example = {
        "success": True,
        "total_steps": 2,
        "retry_count": 5,
        "tools_used": ["terminal"],
        "duration_ms": 1000,
        "tool_calls_count": 1,
    }
    score = scorer.score(example)
    assert score.retry_penalty > 0.0
    assert score.efficiency_score < 0.5


def test_empty_tools_diversity():
    scorer = QualityScorer()
    example = {
        "success": True,
        "total_steps": 1,
        "retry_count": 0,
        "tools_used": [],
        "duration_ms": 100,
        "tool_calls_count": 0,
    }
    score = scorer.score(example)
    assert score.tool_diversity_score == 0.0


def test_score_bounds():
    scorer = QualityScorer()
    example = {
        "success": True,
        "total_steps": 10,
        "retry_count": 0,
        "tools_used": ["a", "b", "c", "d"],
        "duration_ms": 500,
        "tool_calls_count": 4,
    }
    score = scorer.score(example)
    assert 0.0 <= score.overall <= 1.0
