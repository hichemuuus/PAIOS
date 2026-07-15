"""Unified training pipeline v2 — trains micro-models from prepared datasets.

Uses the preparation pipeline (validator → splitter) to process data,
then trains IntentModel and ToolSelectorModel with comprehensive evaluation.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from veyron.config import DATA_DIR
from veyron.intelligence.error_recovery.dataset import ErrorRecoveryDataset
from veyron.intelligence.error_recovery.model import ErrorRecoveryModel
from veyron.intelligence.intent.model import IntentModel
from veyron.intelligence.intent_router.dataset import IntentRouterDataset
from veyron.intelligence.intent_router.model import IntentRouterModel
from veyron.intelligence.memory_retrieval.dataset import MemoryRetrievalDataset
from veyron.intelligence.memory_retrieval.model import MemoryRetrievalModel
from veyron.intelligence.planning.dataset import PlanningDataset
from veyron.intelligence.planning.model import PlanningModel
from veyron.intelligence.tool_selector.model import ToolSelectorModel
from veyron.intelligence.training.dataset import TrainingDataset
from veyron.intelligence.training.evaluation import (
    IntentEvalReport,
    IntentEvaluator,
    ToolSelectorEvalReport,
    ToolSelectorEvaluator,
)
from veyron.intelligence.training.preparation.splitter import DatasetSplitter

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
        error_recovery_model: ErrorRecoveryModel | None = None,
        planning_model: PlanningModel | None = None,
        output_dir: str | Path | None = None,
        version: str | None = None,
    ) -> dict[str, Path]:
        output_path = Path(output_dir) if output_dir else (DATA_DIR / "models")
        output_path.mkdir(parents=True, exist_ok=True)
        ts = version or datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
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

        if error_recovery_model is not None:
            model_path = output_path / f"error_recovery_{ts}.pkl"
            error_recovery_model.save(str(model_path))
            latest = output_path / "error_recovery.pkl"
            if latest.exists():
                latest.unlink()
            import shutil
            shutil.copy(str(model_path), str(latest))
            saved["error_recovery_model"] = model_path

        if planning_model is not None:
            model_path = output_path / f"planning_{ts}.pkl"
            planning_model.save(str(model_path))
            latest = output_path / "planning.pkl"
            if latest.exists():
                latest.unlink()
            import shutil
            shutil.copy(str(model_path), str(latest))
            saved["planning_model"] = model_path

        return saved

    def train_memory_retrieval(
        self,
        dataset: MemoryRetrievalDataset | None = None,
        model: MemoryRetrievalModel | None = None,
        seed: int = 42,
    ) -> tuple[MemoryRetrievalModel, dict[str, Any]]:
        from veyron.intelligence.memory_retrieval.trainer import train_memory_retrieval as _train

        return _train(dataset=dataset, model=model, output_dir=self.output_dir, seed=seed)

    def train_intent_router(
        self,
        dataset: IntentRouterDataset | None = None,
        model: IntentRouterModel | None = None,
        seed: int = 42,
    ) -> tuple[IntentRouterModel, dict[str, Any]]:
        from veyron.intelligence.intent_router.trainer import train_intent_router as _train

        return _train(dataset=dataset, model=model, output_dir=self.output_dir, seed=seed)

    def train_error_recovery(
        self,
        dataset: ErrorRecoveryDataset | None = None,
        model: ErrorRecoveryModel | None = None,
        seed: int = 42,
    ) -> tuple[ErrorRecoveryModel, dict[str, Any]]:
        from veyron.intelligence.error_recovery.trainer import train_error_recovery as _train

        return _train(dataset=dataset, model=model, output_dir=self.output_dir, seed=seed)

    def train_planning(
        self,
        dataset: PlanningDataset | None = None,
        model: PlanningModel | None = None,
        seed: int = 42,
    ) -> tuple[PlanningModel, dict[str, Any]]:
        from veyron.intelligence.planning.trainer import train_planning as _train

        return _train(dataset=dataset, model=model, output_dir=self.output_dir, seed=seed)

    def train_all_models(
        self,
        dataset: TrainingDataset,
        seed: int = 42,
    ) -> dict[str, Any]:
        """Train every micro-model type from the same dataset.

        Trains: intent_classifier, tool_selector, intent_router,
        error_recovery, planning, memory_retrieval.
        Returns a dict mapping model_type -> {model, report}.
        """
        import importlib

        results: dict[str, Any] = {}

        intent_model, intent_report = self.train_intent(dataset, seed=seed)
        results["intent_classifier"] = {"model": intent_model, "report": intent_report.to_dict()}

        ts_model, ts_report = self.train_tool_selector(dataset, seed=seed)
        results["tool_selector"] = {"model": ts_model, "report": ts_report.to_dict()}

        delegate_types = {
            "intent_router": ("veyron.intelligence.intent_router.trainer", "train_intent_router"),
            "error_recovery": ("veyron.intelligence.error_recovery.trainer", "train_error_recovery"),
            "planning": ("veyron.intelligence.planning.trainer", "train_planning"),
            "memory_retrieval": ("veyron.intelligence.memory_retrieval.trainer", "train_memory_retrieval"),
        }
        for model_type, (mod_path, func_name) in delegate_types.items():
            try:
                mod = importlib.import_module(mod_path)
                func = getattr(mod, func_name)
                model, report = func(output_dir=self.output_dir, seed=seed)
                results[model_type] = {"model": model, "report": report}
            except Exception as e:
                logger.warning("train %s skipped: %s", model_type, e)
                results[model_type] = {"model": None, "report": None}

        return results

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
