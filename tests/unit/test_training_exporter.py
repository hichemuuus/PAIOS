"""Tests for TrainingExporter."""

from __future__ import annotations

import json
from pathlib import Path

from paios.intelligence.training.dataset import TrainingDataset, TrainingExample
from paios.intelligence.training.exporter import TrainingExporter, get_exporter, reset_exporter


def _make_dataset(size: int = 3) -> TrainingDataset:
    examples = [
        TrainingExample(
            request=f"request_{i}",
            intent="conversation",
            tools_used=["terminal"],
            success=True,
            duration_ms=1000,
            quality_score=0.8,
            total_steps=2,
            task_id=f"t{i}",
        )
        for i in range(size)
    ]
    return TrainingDataset(examples)


def test_export_dataset_creates_file(tmp_path: Path):
    exporter = TrainingExporter(output_dir=tmp_path)
    dataset = _make_dataset()
    result = exporter.export_dataset(dataset, filename="test.jsonl")
    assert "dataset" in result
    path = result["dataset"]
    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3


def test_export_split_creates_two_files(tmp_path: Path):
    exporter = TrainingExporter(output_dir=tmp_path)
    dataset = _make_dataset(size=10)
    result = exporter.export_dataset(dataset, filename="split.jsonl", split_ratio=0.8)
    assert "train" in result
    assert "test" in result
    assert result["train"].exists()
    assert result["test"].exists()


def test_export_by_category(tmp_path: Path):
    exporter = TrainingExporter(output_dir=tmp_path)
    cat_a = TrainingExample(
        request="cat a", category="system",
        tools_used=[], duration_ms=100, quality_score=0.5, task_id="ca",
    )
    cat_b = TrainingExample(
        request="cat b", category="coding",
        tools_used=[], duration_ms=100, quality_score=0.5, task_id="cb",
    )
    dataset = TrainingDataset([cat_a, cat_b])
    paths = exporter.export_by_category(dataset)
    assert "system" in paths
    assert "coding" in paths
    assert paths["system"].exists()
    assert paths["coding"].exists()


def test_export_summary(tmp_path: Path):
    exporter = TrainingExporter(output_dir=tmp_path)
    dataset = _make_dataset()
    path = exporter.export_summary(dataset)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["total"] == 3


def test_list_exports(tmp_path: Path):
    exporter = TrainingExporter(output_dir=tmp_path)
    dataset = _make_dataset()
    exporter.export_dataset(dataset, filename="list_test.jsonl")
    exports = exporter.list_exports()
    assert len(exports) >= 1
    assert exports[0]["filename"] == "list_test.jsonl"
    assert exports[0]["size_bytes"] > 0


def test_singleton():
    reset_exporter()
    e1 = get_exporter()
    e2 = get_exporter()
    assert e1 is e2
    reset_exporter()
    e3 = get_exporter()
    assert e3 is not e1


def test_exported_jsonl_is_valid(tmp_path: Path):
    exporter = TrainingExporter(output_dir=tmp_path)
    dataset = _make_dataset()
    result = exporter.export_dataset(dataset, filename="valid.jsonl")
    with open(result["dataset"], encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            assert "request" in obj
            assert "intent" in obj
            assert "tools_used" in obj
            assert "success" in obj
            assert "duration_ms" in obj
            assert "quality_score" in obj
