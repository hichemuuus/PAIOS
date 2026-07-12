"""Automatic retraining preparation — scheduler-ready architecture.

Provides:
  - TrainingTrigger: interface for triggering conditions
  - DatasetGrowthDetector: monitors new example count
  - BenchmarkComparator: compares candidate vs production before promotion
  - RetrainingOrchestrator: coordinates the full flow
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paios.config import DATA_DIR
from paios.intelligence.models.registry import ModelRegistry
from paios.intelligence.models.schema import (
    ModelMetadata,
    STATUS_CANDIDATE,
    STATUS_PRODUCTION,
)
from paios.intelligence.training.dataset import TrainingDataset
from paios.intelligence.training.trainer_v2 import TrainingPipelineV2

logger = logging.getLogger(__name__)

REPORTS_DIR = DATA_DIR / "reports"
USER_INTERACTIONS_DIR = DATA_DIR / "training" / "user_interactions"


class TrainingTrigger(ABC):
    """Interface for retraining trigger conditions."""

    @abstractmethod
    def should_trigger(self) -> bool:
        ...

    @abstractmethod
    def describe(self) -> str:
        ...


@dataclass
class NewExampleTrigger(TrainingTrigger):
    """Triggers when new user interaction examples exceed a threshold."""

    min_new_examples: int = 100
    _last_count: int = 0

    def should_trigger(self) -> bool:
        current = self._count_interaction_files()
        new_count = current - self._last_count
        if new_count >= self.min_new_examples:
            self._last_count = current
            return True
        return False

    def describe(self) -> str:
        return f"new_example_threshold={self.min_new_examples}"

    @staticmethod
    def _count_interaction_files() -> int:
        if not USER_INTERACTIONS_DIR.exists():
            return 0
        return len(list(USER_INTERACTIONS_DIR.glob("*.jsonl")))

    def update_last_count(self) -> None:
        self._last_count = self._count_interaction_files()


class DatasetGrowthDetector:
    """Detects whether the training dataset has grown enough to justify retraining."""

    def __init__(self, min_growth_pct: float = 10.0) -> None:
        self.min_growth_pct = min_growth_pct

    def should_retrain(
        self,
        current_dataset_size: int,
        last_training_size: int,
    ) -> bool:
        if last_training_size <= 0:
            return current_dataset_size > 0
        growth = (current_dataset_size - last_training_size) / last_training_size * 100
        logger.debug(
            "dataset growth: %d -> %d (%.1f%%)",
            last_training_size, current_dataset_size, growth,
        )
        return growth >= self.min_growth_pct


class BenchmarkComparator:
    """Compares candidate model against production model before promotion."""

    def __init__(self) -> None:
        self.pipeline = TrainingPipelineV2()

    def compare(
        self,
        candidate_metrics: dict[str, float],
        production_metrics: dict[str, float] | None,
        model_type: str,
    ) -> BenchmarkComparisonResult:
        if production_metrics is None:
            return BenchmarkComparisonResult(
                is_better=True,
                reason="no production model to compare against",
                deltas={k: v for k, v in candidate_metrics.items()},
            )

        deltas: dict[str, float] = {}
        all_better_or_equal = True
        details: list[str] = []

        for key, candidate_val in candidate_metrics.items():
            prod_val = production_metrics.get(key, 0.0)
            delta = candidate_val - prod_val
            deltas[key] = round(delta, 4)

            higher_is_better = key not in ("latency_ms", "error_rate")
            if higher_is_better:
                if delta > 0:
                    details.append(f"{key}: +{delta:.4f}")
                elif delta < 0:
                    all_better_or_equal = False
                    details.append(f"{key}: {delta:.4f} (worse)")
            else:
                if delta < 0:
                    details.append(f"{key}: {delta:.4f} (improved)")
                elif delta > 0:
                    all_better_or_equal = False
                    details.append(f"{key}: +{delta:.4f} (worse)")

        return BenchmarkComparisonResult(
            is_better=all_better_or_equal,
            reason="; ".join(details) if details else "all metrics equal",
            deltas=deltas,
        )


@dataclass
class BenchmarkComparisonResult:
    is_better: bool
    reason: str
    deltas: dict[str, float] = field(default_factory=dict)


class RetrainingOrchestrator:
    """Coordinates the full retraining flow: trigger -> validate -> train -> benchmark -> promote."""

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        trigger: TrainingTrigger | None = None,
        growth_detector: DatasetGrowthDetector | None = None,
        comparator: BenchmarkComparator | None = None,
    ) -> None:
        self.registry = registry or ModelRegistry()
        self.trigger = trigger
        self.growth_detector = growth_detector or DatasetGrowthDetector()
        self.comparator = comparator or BenchmarkComparator()
        self.pipeline = TrainingPipelineV2()

    def prepare_retrain(
        self,
        dataset: TrainingDataset,
        model_type: str = "intent_classifier",
        force: bool = False,
    ) -> RetrainPlan:
        """Prepare a retraining plan without executing it. Analyzes conditions and returns a plan."""
        production_md = self.registry.get_production(model_type)
        current_size = len(dataset)

        trigger_ready = True
        if self.trigger and not force:
            trigger_ready = self.trigger.should_trigger()

        last_size = production_md.dataset_size if production_md else 0
        growth_ready = self.growth_detector.should_retrain(current_size, last_size) or force

        issues: list[str] = []
        if not trigger_ready:
            issues.append(f"trigger not satisfied ({self.trigger.describe()})" if self.trigger else "")
        if not growth_ready:
            issues.append(f"insufficient growth ({current_size} vs {last_size})")

        ready = (trigger_ready or self.trigger is None) and growth_ready

        return RetrainPlan(
            ready=ready,
            model_type=model_type,
            current_dataset_size=current_size,
            last_training_size=last_size,
            production_version=production_md.version if production_md else None,
            production_metrics=production_md.metrics if production_md else None,
            issues=issues,
            force=force,
        )

    def execute_retrain(
        self,
        dataset: TrainingDataset,
        model_type: str = "intent_classifier",
        force: bool = False,
    ) -> RetrainResult:
        """Execute a full retrain cycle: train -> benchmark -> promote if better."""
        plan = self.prepare_retrain(dataset, model_type, force=force)
        if not plan.ready and not force:
            return RetrainResult(success=False, plan=plan, error="retrain not ready")

        # Train candidate model.
        try:
            if model_type == "intent_classifier":
                model, report = self.pipeline.train_intent(dataset)
                candidate_metrics = {
                    "accuracy": report.accuracy,
                    "macro_f1": report.macro_f1,
                }
            elif model_type == "tool_selector":
                model, report = self.pipeline.train_tool_selector(dataset)
                candidate_metrics = {
                    "precision_at_1": report.precision_at_1,
                    "recall_at_3": report.recall_at_3,
                }
            else:
                return RetrainResult(success=False, plan=plan, error=f"unknown model_type: {model_type}")
        except Exception as e:
            logger.error("training failed: %s", e)
            return RetrainResult(success=False, plan=plan, error=f"training failed: {e}")

        # Compare against production.
        comparison = self.comparator.compare(
            candidate_metrics, plan.production_metrics, model_type,
        )

        if not comparison.is_better and not force:
            return RetrainResult(
                success=False,
                plan=plan,
                error=f"candidate not better: {comparison.reason}",
                candidate_metrics=candidate_metrics,
                comparison=comparison,
            )

        # Save candidate and register.
        version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        saved = self.pipeline.save_models(
            model if model_type == "intent_classifier" else None,
            model if model_type == "tool_selector" else None,
        )
        model_path = str(saved.get(
            "intent_model" if model_type == "intent_classifier" else "tool_selector_model", ""
        ))

        metadata = ModelMetadata(
            name=f"{model_type}_v{version}",
            version=version,
            model_type=model_type,
            dataset_hash="",
            dataset_size=len(dataset),
            metrics=candidate_metrics,
            status=STATUS_CANDIDATE,
            path=model_path,
            parent_version=plan.production_version or "",
        )
        self.registry.register(metadata)

        return RetrainResult(
            success=True,
            plan=plan,
            candidate_metrics=candidate_metrics,
            comparison=comparison,
            metadata=metadata,
            model=model,
        )

    def promote_if_better(
        self,
        dataset: TrainingDataset,
        model_type: str = "intent_classifier",
    ) -> RetrainResult:
        """Convenience: execute retrain and promote the candidate if it beats production."""
        result = self.execute_retrain(dataset, model_type)
        if result.success and result.metadata:
            self.registry.promote(model_type, result.metadata.version)
            result.promoted = True
        return result


@dataclass
class RetrainPlan:
    ready: bool
    model_type: str
    current_dataset_size: int
    last_training_size: int
    production_version: str | None = None
    production_metrics: dict[str, float] | None = None
    issues: list[str] = field(default_factory=list)
    force: bool = False


@dataclass
class RetrainResult:
    success: bool
    plan: RetrainPlan | None = None
    error: str = ""
    candidate_metrics: dict[str, float] | None = None
    comparison: BenchmarkComparisonResult | None = None
    metadata: ModelMetadata | None = None
    model: Any = None
    promoted: bool = False
