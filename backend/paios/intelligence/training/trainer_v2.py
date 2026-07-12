"""Unified training pipeline v2 — trains micro-models from prepared datasets.

Uses the preparation pipeline (validator → splitter) to process data,
then trains IntentModel and ToolSelectorModel with comprehensive evaluation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paios.config import DATA_DIR
from paios.intelligence.intent.model import IntentModel
from paios.intelligence.tool_selector.model import ToolSelectorModel
from paios.intelligence.training.dataset import TrainingDataset, TrainingExample
from paios.intelligence.training.evaluation import (
    IntentEvaluator,
    IntentEvalReport,
    ToolSelectorEvaluator,
    ToolSelectorEvalReport,
)
from paios.intelligence.training.preparation.splitter import DatasetSplitter
from paios.intelligence.training.preparation.validator import DatasetValidator

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = DATA_DIR / "models"


class TrainingPipelineV2:
    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_MODEL_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def train_intent(
        self,
        dataset: TrainingDataset,
        test_dataset: TrainingDataset | None = None,
        model_name: str = "intent_classifier_v2",
        seed: int = 42,
    ) -> tuple[IntentModel, IntentEvalReport]:
        from paios.intelligence.training.dataset import TrainingDataset

        if test_dataset is None:
            splitter = DatasetSplitter()
            dataset, test_dataset = splitter.stratified_split(dataset, train_ratio=0.8, seed=seed)

        train_texts = [ex.request for ex in dataset.examples if ex.request]
        train_labels = [ex.intent for ex in dataset.examples if ex.request]
        test_texts = [ex.request for ex in test_dataset.examples if ex.request]
        test_labels = [ex.intent for ex in test_dataset.examples if ex.request]

        model = IntentModel()
        model.fit(train_texts, train_labels)

        report = IntentEvaluator().evaluate(model, test_texts, test_labels)
        return model, report

    def train_tool_selector(
        self,
        dataset: TrainingDataset,
        test_dataset: TrainingDataset | None = None,
        model_name: str = "tool_selector_v2",
        seed: int = 42,
    ) -> tuple[ToolSelectorModel, ToolSelectorEvalReport]:
        if test_dataset is None:
            splitter = DatasetSplitter()
            dataset, test_dataset = splitter.stratified_split(dataset, train_ratio=0.8, seed=seed)

        train_texts = [ex.request for ex in dataset.examples if ex.request]
        train_targets = [ex.tools_used for ex in dataset.examples if ex.request]
        test_texts = [ex.request for ex in test_dataset.examples if ex.request]
        test_targets = [ex.tools_used for ex in test_dataset.examples if ex.request]

        model = ToolSelectorModel()
        model.fit(train_texts, train_targets)

        report = ToolSelectorEvaluator().evaluate(model, test_texts, test_targets)
        return model, report

    def train_all(
        self,
        dataset: TrainingDataset,
        test_dataset: TrainingDataset | None = None,
        seed: int = 42,
    ) -> dict[str, Any]:
        intent_model, intent_report = self.train_intent(dataset, test_dataset, seed=seed)
        ts_model, ts_report = self.train_tool_selector(dataset, test_dataset, seed=seed)
        return {
            "intent_model": intent_model,
            "tool_selector_model": ts_model,
            "intent_report": intent_report.to_dict(),
            "tool_selector_report": ts_report.to_dict(),
        }

    def save_models(
        self,
        intent_model: IntentModel | None = None,
        tool_selector_model: ToolSelectorModel | None = None,
        output_dir: str | Path | None = None,
        version: str | None = None,
    ) -> dict[str, Path]:
        output_path = Path(output_dir) if output_dir else (DATA_DIR / "models")
        output_path.mkdir(parents=True, exist_ok=True)
        ts = version or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        saved: dict[str, Path] = {}

        if intent_model is not None:
            model_path = output_path / f"intent_classifier_{ts}.pkl"
            intent_model.save(str(model_path))
            latest = output_path / "intent_classifier.pkl"
            if latest.exists():
                latest.unlink()
            import shutil
            shutil.copy(str(model_path), str(latest))
            saved["intent_model"] = model_path

        if tool_selector_model is not None:
            model_path = output_path / f"tool_selector_{ts}.pkl"
            tool_selector_model.save(str(model_path))
            latest = output_path / "tool_selector.pkl"
            if latest.exists():
                latest.unlink()
            import shutil
            shutil.copy(str(model_path), str(latest))
            saved["tool_selector_model"] = model_path

        return saved

    def save_reports(
        self,
        intent_report: IntentEvalReport | None = None,
        ts_report: ToolSelectorEvalReport | None = None,
        output_dir: str | Path | None = None,
    ) -> dict[str, Path]:
        output_path = Path(output_dir) if output_dir else (DATA_DIR / "models")
        output_path.mkdir(parents=True, exist_ok=True)
        saved: dict[str, Path] = {}

        if intent_report is not None:
            path = output_path / "training_report_v2.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(intent_report.to_dict(), f, indent=2, default=str)
            saved["intent_report"] = path

        if ts_report is not None:
            path = output_path / "tool_selector_report_v2.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(ts_report.to_dict(), f, indent=2, default=str)
            saved["tool_selector_report"] = path

        return saved
