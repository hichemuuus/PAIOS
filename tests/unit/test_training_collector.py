"""Tests for TrainingDataCollector."""

from __future__ import annotations

from datetime import UTC

import pytest
from veyron.db.models import Task, TaskStatus, ToolInvocation
from veyron.intelligence.training.collector import TrainingDataCollector, _infer_intent


@pytest.fixture(autouse=True)
def _db(fresh_db):
    pass


def _seed_task(
    public_id: str,
    request: str,
    status: TaskStatus = TaskStatus.COMPLETED,
    mode: str = "react",
    total_steps: int = 3,
    retry_count: int = 0,
    tool_count: int = 1,
    started: bool = True,
) -> None:
    from datetime import datetime

    from veyron.db.base import sync_session_scope

    with sync_session_scope() as session:
        task = Task(
            public_id=public_id,
            request=request,
            status=status,
            mode=mode,
            total_steps=total_steps,
            retry_count=retry_count,
            tool_count=tool_count,
        )
        if started:
            task.started_at = datetime.now(UTC).replace(tzinfo=None)
            task.finished_at = datetime.now(UTC).replace(tzinfo=None)
        session.add(task)

    from veyron.db.base import sync_session_scope
    with sync_session_scope() as session:
        inv = ToolInvocation(
            task_public_id=public_id,
            tool_name="terminal",
            permission="CONFIRM",
            inputs="{}",
            result="ok",
            ok=True,
            duration_ms=100,
        )
        session.add(inv)


def test_collect_successful_returns_examples():
    _seed_task("t1", "show cpu usage")
    collector = TrainingDataCollector()
    dataset = collector.collect_successful(limit=100)
    assert len(dataset) > 0
    ex = dataset[0]
    assert ex.request == "show cpu usage"
    assert ex.success is True
    assert ex.quality_score > 0.0
    assert ex.task_id == "t1"


def test_collect_skips_tasks_without_request():
    _seed_task("t2", "")
    collector = TrainingDataCollector()
    dataset = collector.collect_successful(limit=100)
    ids = [e.task_id for e in dataset]
    assert "t2" not in ids


def test_collect_failed_tasks():
    _seed_task("t3", "do something", status=TaskStatus.FAILED, retry_count=3)
    collector = TrainingDataCollector()
    dataset = collector.collect_successful(limit=100)
    failed = [e for e in dataset if e.task_id == "t3"]
    if failed:
        assert not failed[0].success


def test_collect_respects_limit():
    for i in range(5):
        _seed_task(f"t_limit_{i}", f"request {i}")
    collector = TrainingDataCollector()
    dataset = collector.collect_successful(limit=3)
    assert len(dataset) <= 3


def test_collect_min_quality_filter():
    _seed_task("t_high", "good request")
    collector = TrainingDataCollector()
    all_data = collector.collect_successful(limit=100, min_quality=0.0)
    high_only = collector.collect_successful(limit=100, min_quality=0.9)
    assert len(high_only) <= len(all_data)


def test_collect_all_returns_dict():
    _seed_task("t_all", "some request")
    collector = TrainingDataCollector()
    result = collector.collect_all(limit=100)
    assert "all" in result
    assert len(result["all"]) > 0


def test_infer_intent():
    assert _infer_intent("what is the weather?", []) == "question_answering"
    assert _infer_intent("show cpu", ["system_monitor"]) == "system_management"
    assert _infer_intent("read file", ["filesystem_read"]) == "file_operation"
    assert _infer_intent("write code", []) == "coding_task"
    assert _infer_intent("analyze my project", []) == "project_analysis"
    assert _infer_intent("hello", []) == "conversation"


def test_collect_includes_metadata():
    _seed_task("t_meta", "analyze project", mode="plan", total_steps=5, retry_count=1, tool_count=2)
    collector = TrainingDataCollector()
    dataset = collector.collect_successful(limit=100)
    meta_tasks = [e for e in dataset if e.task_id == "t_meta"]
    if meta_tasks:
        ex = meta_tasks[0]
        assert ex.mode == "plan"
        assert ex.total_steps == 5
        assert ex.retry_count == 1
        assert "quality_details" in ex.metadata
