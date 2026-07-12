"""Dataset format for parameter extraction training.

Provides containers and loading utilities for parameter extraction examples.
The dataset is built from the synthetic training data which already contains
``expected_parameters`` per example.

Not yet used for training — this is the data contract for future implementation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from paios.intelligence.parameter_extraction.schema import ParameterExample

logger = logging.getLogger(__name__)


class ParameterExtractionDataset:
    """Container for parameter extraction examples."""

    def __init__(self, examples: list[ParameterExample] | None = None) -> None:
        self.examples: list[ParameterExample] = examples or []

    def add(self, example: ParameterExample) -> None:
        self.examples.append(example)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> ParameterExample:
        return self.examples[idx]

    @classmethod
    def from_synthetic_jsonl(cls, path: str | Path) -> ParameterExtractionDataset:
        """Load parameter examples from the synthetic training JSONL.

        Each record in the JSONL should contain ``request``, ``expected_tools``,
        and ``expected_parameters`` fields.
        """
        path = Path(path)
        dataset = cls()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                request = record.get("request", "")
                tools = record.get("expected_tools", [])
                params = record.get("expected_parameters", {})
                intent = record.get("intent", "")
                difficulty = record.get("difficulty", "easy")

                if not request:
                    continue

                for tool in tools:
                    dataset.add(ParameterExample(
                        request=request,
                        tool_name=tool,
                        expected_parameters=params,
                        intent_category=intent,
                        difficulty=difficulty,
                    ))

        logger.info("Loaded %d parameter extraction examples from %s", len(dataset), path)
        return dataset

    def to_jsonl(self, path: str | Path) -> None:
        """Serialise to JSONL."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for ex in self.examples:
                f.write(json.dumps({
                    "request": ex.request,
                    "tool_name": ex.tool_name,
                    "expected_parameters": ex.expected_parameters,
                    "intent_category": ex.intent_category,
                    "difficulty": ex.difficulty,
                }, ensure_ascii=False) + "\n")
        logger.info("Saved %d parameter extraction examples to %s", len(self.examples), path)

    def summary(self) -> dict[str, Any]:
        if not self.examples:
            return {"total": 0}
        tool_counts: dict[str, int] = {}
        for ex in self.examples:
            tool_counts[ex.tool_name] = tool_counts.get(ex.tool_name, 0) + 1
        return {
            "total": len(self.examples),
            "tools": tool_counts,
            "unique_requests": len({ex.request for ex in self.examples}),
        }
