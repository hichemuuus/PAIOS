"""Dataset splitter — stratified train/test splitting.

Performs an 80/20 stratified split that preserves the intent category
distribution in both splits.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from veyron.intelligence.training.dataset import TrainingDataset, TrainingExample

logger = logging.getLogger(__name__)

INTENT_CATEGORIES = [
    "question_answering",
    "coding_task",
    "project_analysis",
    "file_operation",
    "tool_execution",
    "planning_task",
    "debugging",
    "system_management",
    "research",
    "conversation",
    "memory_recall",
    "user_preference_update",
    "context_request",
]


class DatasetSplitter:
    def stratified_split(
        self,
        dataset: TrainingDataset,
        train_ratio: float = 0.8,
        seed: int = 42,
    ) -> tuple[TrainingDataset, TrainingDataset]:
        if train_ratio <= 0 or train_ratio >= 1:
            raise ValueError("train_ratio must be between 0 and 1 (exclusive)")

        import random
        rng = random.Random(seed)

        groups: dict[str, list[TrainingExample]] = defaultdict(list)
        for ex in dataset.examples:
            cat = ex.intent or ex.category or "general"
            groups[cat].append(ex)

        train: list[TrainingExample] = []
        test: list[TrainingExample] = []
        category_counts: dict[str, dict[str, int]] = {}

        for cat, examples in sorted(groups.items()):
            rng.shuffle(examples)
            split_idx = max(1, int(len(examples) * train_ratio))
            if split_idx >= len(examples):
                split_idx = len(examples) - 1 if len(examples) > 1 else 0
            train.extend(examples[:split_idx])
            test.extend(examples[split_idx:])
            category_counts[cat] = {"total": len(examples), "train": split_idx, "test": len(examples) - split_idx}

        rng.shuffle(train)
        rng.shuffle(test)

        train_ds = TrainingDataset(train)
        test_ds = TrainingDataset(test)

        logger.info(
            "stratified split: %d train, %d test (ratio=%.2f)",
            len(train_ds), len(test_ds), train_ratio,
        )
        self._log_split_summary(category_counts)

        return train_ds, test_ds

    def split_by_field(
        self,
        dataset: TrainingDataset,
        field: str = "difficulty",
        train_ratio: float = 0.8,
        seed: int = 42,
    ) -> tuple[TrainingDataset, TrainingDataset]:
        import random
        rng = random.Random(seed)

        groups: dict[str, list[TrainingExample]] = defaultdict(list)
        for ex in dataset.examples:
            val = ex.metadata.get(field, "unknown") if ex.metadata else "unknown"
            groups[val].append(ex)

        train: list[TrainingExample] = []
        test: list[TrainingExample] = []

        for cat, examples in sorted(groups.items()):
            rng.shuffle(examples)
            split_idx = max(1, int(len(examples) * train_ratio))
            if split_idx >= len(examples):
                split_idx = len(examples) - 1 if len(examples) > 1 else 0
            train.extend(examples[:split_idx])
            test.extend(examples[split_idx:])

        rng.shuffle(train)
        rng.shuffle(test)
        return TrainingDataset(train), TrainingDataset(test)

    def _log_split_summary(self, category_counts: dict[str, dict[str, int]]) -> None:
        for cat, counts in sorted(category_counts.items()):
            pct = round(counts["train"] / max(counts["total"], 1) * 100, 1)
            logger.debug(
                "  %-25s %3d total → %3d train (%5.1f%%) / %3d test",
                cat, counts["total"], counts["train"], pct, counts["test"],
            )


def load_jsonl_as_examples(path: str | Path, field_map: dict[str, str] | None = None) -> TrainingDataset:
    import json
    from pathlib import Path

    path = Path(path)
    examples: list[TrainingExample] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if field_map:
                mapped = {}
                for src_key, tgt_key in field_map.items():
                    if src_key in record:
                        mapped[tgt_key] = record[src_key]
                record.update(mapped)
            ex = TrainingExample(
                request=record.get("request", ""),
                intent=record.get("intent", ""),
                tools_used=record.get("expected_tools", record.get("tools_used", [])),
                category=record.get("intent", record.get("category", "general")),
                duration_ms=record.get("duration_ms", 0),
                quality_score=record.get("quality_score", 0.0),
                total_steps=record.get("total_steps", 0),
                retry_count=record.get("retry_count", 0),
                tool_calls_count=record.get("tool_calls_count", 0),
                mode=record.get("mode", record.get("difficulty", "react")),
                success=record.get("success", True),
                error=record.get("error"),
                task_id=record.get("task_id", ""),
                metadata={
                    "difficulty": record.get("difficulty", ""),
                    "planning_required": record.get("planning_required", False),
                    "expected_parameters": record.get("expected_parameters", {}),
                },
            )
            examples.append(ex)
    return TrainingDataset(examples)
