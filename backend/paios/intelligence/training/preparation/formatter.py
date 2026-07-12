"""Dataset formatter — exports datasets for specific micro-model training tasks.

Produces JSONL files optimised for:
  1. Intent classification  — (text → intent category)
  2. Tool selection          — (text → relevant tool set)
  3. Parameter generation    — (text + tool → expected parameters)
  4. Planner training        — (text → planning_required + difficulty)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paios.config import DATA_DIR
from paios.intelligence.training.dataset import TrainingDataset, TrainingExample

logger = logging.getLogger(__name__)


class DatasetFormatter:
    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else (DATA_DIR / "training" / "formatted")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def format_intent_classification(
        self,
        dataset: TrainingDataset,
        filename: str | None = None,
    ) -> Path:
        filename = filename or f"intent_classification_{self._ts()}.jsonl"
        path = self.output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            for ex in dataset.examples:
                if not ex.request:
                    continue
                record = {
                    "text": ex.request,
                    "intent": ex.intent or "unknown",
                    "difficulty": ex.metadata.get("difficulty", "") if ex.metadata else "",
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info("wrote %d intent examples to %s", len(dataset), path)
        return path

    def format_tool_selection(
        self,
        dataset: TrainingDataset,
        filename: str | None = None,
    ) -> Path:
        filename = filename or f"tool_selection_{self._ts()}.jsonl"
        path = self.output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            for ex in dataset.examples:
                if not ex.request:
                    continue
                record = {
                    "text": ex.request,
                    "tools": sorted(ex.tools_used),
                    "intent_hint": ex.intent or "",
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info("wrote %d tool selection examples to %s", len(dataset), path)
        return path

    def format_parameter_generation(
        self,
        dataset: TrainingDataset,
        filename: str | None = None,
    ) -> Path:
        filename = filename or f"parameter_generation_{self._ts()}.jsonl"
        path = self.output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            for ex in dataset.examples:
                if not ex.request or not ex.tools_used:
                    continue
                params = ex.metadata.get("expected_parameters", {}) if ex.metadata else {}
                for tool in ex.tools_used:
                    record = {
                        "text": ex.request,
                        "tool": tool,
                        "parameters": params,
                        "intent": ex.intent or "",
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info("wrote %d parameter examples to %s", len(dataset), path)
        return path

    def format_planner_training(
        self,
        dataset: TrainingDataset,
        filename: str | None = None,
    ) -> Path:
        filename = filename or f"planner_training_{self._ts()}.jsonl"
        path = self.output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            for ex in dataset.examples:
                if not ex.request:
                    continue
                planning_required = False
                difficulty = "easy"
                if ex.metadata:
                    planning_required = ex.metadata.get("planning_required", False)
                    difficulty = ex.metadata.get("difficulty", "easy")
                record = {
                    "text": ex.request,
                    "planning_required": planning_required,
                    "difficulty": difficulty,
                    "mode": "plan" if planning_required else "react",
                    "intent": ex.intent or "",
                    "tools": sorted(ex.tools_used),
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info("wrote %d planner examples to %s", len(dataset), path)
        return path

    def format_all(
        self,
        dataset: TrainingDataset,
        prefix: str = "dataset",
    ) -> dict[str, Path]:
        return {
            "intent_classification": self.format_intent_classification(dataset, filename=f"{prefix}_intent.jsonl"),
            "tool_selection": self.format_tool_selection(dataset, filename=f"{prefix}_tool_selection.jsonl"),
            "parameter_generation": self.format_parameter_generation(dataset, filename=f"{prefix}_params.jsonl"),
            "planner_training": self.format_planner_training(dataset, filename=f"{prefix}_planner.jsonl"),
        }

    def _ts(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
