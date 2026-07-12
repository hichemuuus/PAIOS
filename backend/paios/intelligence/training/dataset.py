"""Training dataset — container for collected examples with filtering and splitting.

Provides:
  - TrainingExample: a single labeled record
  - UserInteraction: a single user interaction record from real usage
  - TrainingDataset: a collection with dedup, split, and JSONL serialisation
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

USER_INTERACTIONS_DIR = Path(__file__).resolve().parents[4] / "data" / "training" / "user_interactions"


@dataclass
class TrainingExample:
    request: str
    intent: str = ""
    tools_used: list[str] = field(default_factory=list)
    success: bool = True
    duration_ms: int = 0
    quality_score: float = 0.0
    total_steps: int = 0
    retry_count: int = 0
    tool_calls_count: int = 0
    mode: str = "react"
    error: str | None = None
    task_id: str = ""
    category: str = "general"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        raw = f"{self.request}|{'|'.join(sorted(self.tools_used))}|{self.intent}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "intent": self.intent,
            "tools_used": self.tools_used,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "quality_score": self.quality_score,
            "total_steps": self.total_steps,
            "retry_count": self.retry_count,
            "tool_calls_count": self.tool_calls_count,
            "mode": self.mode,
            "error": self.error,
            "task_id": self.task_id,
            "category": self.category,
            "metadata": self.metadata,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingExample:
        return cls(
            request=data.get("request", ""),
            intent=data.get("intent", ""),
            tools_used=data.get("tools_used", []),
            success=data.get("success", True),
            duration_ms=data.get("duration_ms", 0),
            quality_score=data.get("quality_score", 0.0),
            total_steps=data.get("total_steps", 0),
            retry_count=data.get("retry_count", 0),
            tool_calls_count=data.get("tool_calls_count", 0),
            mode=data.get("mode", "react"),
            error=data.get("error"),
            task_id=data.get("task_id", ""),
            category=data.get("category", "general"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class UserInteraction:
    """A single user interaction record from real usage."""
    request: str
    detected_intent: str = ""
    selected_tools: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    quality_score: float = 0.0
    timestamp: str = ""
    task_id: str = ""
    mode: str = "react"
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "detected_intent": self.detected_intent,
            "selected_tools": self.selected_tools,
            "parameters": self.parameters,
            "result": self.result,
            "quality_score": self.quality_score,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "mode": self.mode,
            "success": self.success,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserInteraction:
        return cls(
            request=data.get("request", ""),
            detected_intent=data.get("detected_intent", ""),
            selected_tools=data.get("selected_tools", []),
            parameters=data.get("parameters", {}),
            result=data.get("result", ""),
            quality_score=data.get("quality_score", 0.0),
            timestamp=data.get("timestamp", ""),
            task_id=data.get("task_id", ""),
            mode=data.get("mode", "react"),
            success=data.get("success", True),
            metadata=data.get("metadata", {}),
        )

    def to_training_example(self) -> TrainingExample:
        return TrainingExample(
            request=self.request,
            intent=self.detected_intent,
            tools_used=self.selected_tools,
            success=self.success,
            quality_score=self.quality_score,
            mode=self.mode,
            task_id=self.task_id,
            category=self.detected_intent,
            metadata={**self.metadata, "source": "user_interaction"},
        )


def save_user_interaction(
    interaction: UserInteraction,
    directory: str | Path | None = None,
) -> Path:
    """Append a single user interaction to the daily JSONL file."""
    directory = Path(directory or USER_INTERACTIONS_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = directory / f"interactions_{date_str}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(interaction.to_dict(), ensure_ascii=False, default=str) + "\n")
    return path


def load_user_interactions(
    directory: str | Path | None = None,
) -> list[UserInteraction]:
    """Load all user interactions from the directory, sorted by timestamp."""
    directory = Path(directory or USER_INTERACTIONS_DIR)
    if not directory.exists():
        return []
    interactions: list[UserInteraction] = []
    for p in sorted(directory.glob("*.jsonl")):
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    interactions.append(UserInteraction.from_dict(json.loads(line)))
    interactions.sort(key=lambda x: x.timestamp)
    return interactions


def user_interactions_to_dataset(
    directory: str | Path | None = None,
    min_quality: float = 0.0,
    only_successful: bool = False,
    max_examples: int = 0,
) -> TrainingDataset:
    """Convert stored user interactions to a TrainingDataset with optional filtering."""
    interactions = load_user_interactions(directory)
    examples = [ui.to_training_example() for ui in interactions]
    dataset = TrainingDataset(examples)
    if min_quality > 0.0 or only_successful or max_examples > 0:
        dataset = dataset.filter(
            min_quality=min_quality,
            only_successful=only_successful,
            max_examples=max_examples,
        )
    dataset = dataset.deduplicate()
    return dataset


class TrainingDataset:
    def __init__(self, examples: list[TrainingExample] | None = None) -> None:
        self.examples: list[TrainingExample] = examples or []

    def add(self, example: TrainingExample) -> None:
        self.examples.append(example)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> TrainingExample:
        return self.examples[idx]

    def filter(
        self,
        min_quality: float = 0.0,
        only_successful: bool = False,
        max_examples: int = 0,
    ) -> TrainingDataset:
        filtered = self.examples
        if only_successful:
            filtered = [e for e in filtered if e.success]
        if min_quality > 0.0:
            filtered = [e for e in filtered if e.quality_score >= min_quality]
        if max_examples > 0:
            filtered = filtered[:max_examples]
        return TrainingDataset(filtered)

    def deduplicate(self) -> TrainingDataset:
        seen: set[str] = set()
        deduped: list[TrainingExample] = []
        for ex in self.examples:
            h = ex.content_hash
            if h not in seen:
                seen.add(h)
                deduped.append(ex)
        return TrainingDataset(deduped)

    def split(self, ratio: float = 0.8) -> tuple[TrainingDataset, TrainingDataset]:
        split_idx = int(len(self.examples) * ratio)
        return (
            TrainingDataset(self.examples[:split_idx]),
            TrainingDataset(self.examples[split_idx:]),
        )

    def by_category(self) -> dict[str, TrainingDataset]:
        groups: dict[str, TrainingDataset] = {}
        for ex in self.examples:
            cat = ex.category or "general"
            if cat not in groups:
                groups[cat] = TrainingDataset()
            groups[cat].add(ex)
        return groups

    def summary(self) -> dict[str, Any]:
        if not self.examples:
            return {"total": 0}
        successful = sum(1 for e in self.examples if e.success)
        return {
            "total": len(self.examples),
            "successful": successful,
            "failed": len(self.examples) - successful,
            "avg_quality": round(
                sum(e.quality_score for e in self.examples) / len(self.examples), 4
            ),
            "categories": list(self.by_category().keys()),
            "unique_tools": sorted(
                set(t for e in self.examples for t in e.tools_used)
            ),
        }

    def to_jsonl(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for ex in self.examples:
                f.write(json.dumps(ex.to_dict(), ensure_ascii=False, default=str) + "\n")
        logger.info("saved %d examples to %s", len(self.examples), path)
        return path

    @classmethod
    def from_jsonl(cls, path: str | Path) -> TrainingDataset:
        examples: list[TrainingExample] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    examples.append(TrainingExample.from_dict(json.loads(line)))
        return cls(examples)
