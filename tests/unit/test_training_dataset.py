"""Tests for TrainingDataset and TrainingExample."""

from __future__ import annotations

import json
from pathlib import Path

from paios.intelligence.training.dataset import TrainingDataset, TrainingExample


def _make_example(request: str, quality: float = 0.8, success: bool = True) -> TrainingExample:
    return TrainingExample(
        request=request,
        intent="conversation",
        tools_used=["terminal"],
        success=success,
        duration_ms=1000,
        quality_score=quality,
        total_steps=2,
        task_id="test_id",
    )


def test_add_and_len():
    dataset = TrainingDataset()
    assert len(dataset) == 0
    dataset.add(_make_example("hello"))
    assert len(dataset) == 1


def test_filter_by_quality():
    dataset = TrainingDataset([
        _make_example("a", quality=0.9),
        _make_example("b", quality=0.5),
        _make_example("c", quality=0.3),
    ])
    filtered = dataset.filter(min_quality=0.6)
    assert len(filtered) == 1
    assert filtered[0].request == "a"


def test_filter_successful_only():
    dataset = TrainingDataset([
        _make_example("a", success=True),
        _make_example("b", success=False),
    ])
    filtered = dataset.filter(only_successful=True)
    assert len(filtered) == 1
    assert filtered[0].request == "a"


def test_filter_max_examples():
    dataset = TrainingDataset([
        _make_example("a"),
        _make_example("b"),
        _make_example("c"),
    ])
    filtered = dataset.filter(max_examples=2)
    assert len(filtered) == 2


def test_deduplicate():
    dataset = TrainingDataset([
        _make_example("hello world"),
        _make_example("hello world"),
        _make_example("different"),
    ])
    deduped = dataset.deduplicate()
    assert len(deduped) == 2


def test_split():
    dataset = TrainingDataset([
        _make_example(f"request_{i}") for i in range(10)
    ])
    train, test = dataset.split(ratio=0.8)
    assert len(train) == 8
    assert len(test) == 2


def test_summary():
    dataset = TrainingDataset([
        _make_example("a", quality=0.9, success=True),
        _make_example("b", quality=0.4, success=False),
    ])
    summary = dataset.summary()
    assert summary["total"] == 2
    assert summary["successful"] == 1
    assert summary["failed"] == 1
    assert summary["avg_quality"] == 0.65


def test_content_hash():
    a = _make_example("hello")
    b = _make_example("hello")
    assert a.content_hash == b.content_hash
    c = _make_example("different")
    assert a.content_hash != c.content_hash


def test_to_dict_roundtrip():
    ex = _make_example("test request", quality=0.75)
    d = ex.to_dict()
    restored = TrainingExample.from_dict(d)
    assert restored.request == ex.request
    assert restored.quality_score == ex.quality_score
    assert restored.tools_used == ex.tools_used


def test_jsonl_roundtrip(tmp_path: Path):
    dataset = TrainingDataset([
        _make_example("example_1", quality=0.9),
        _make_example("example_2", quality=0.8),
    ])
    path = tmp_path / "test.jsonl"
    dataset.to_jsonl(path)

    loaded = TrainingDataset.from_jsonl(path)
    assert len(loaded) == 2
    assert loaded[0].request == "example_1"
    assert loaded[1].quality_score == 0.8
