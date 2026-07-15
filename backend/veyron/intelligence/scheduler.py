"""Intelligence scheduler — background retraining loop.

Periodically checks dataset growth, triggers retraining, benchmarks
candidate models, and promotes if better.
"""

from __future__ import annotations

import asyncio
import logging

from veyron.intelligence.training.dataset import TrainingDataset, load_user_interactions
from veyron.intelligence.training.retrain import (
    DatasetGrowthDetector,
    RetrainingOrchestrator,
)

logger = logging.getLogger(__name__)


class IntelligenceScheduler:
    """Background scheduler that periodically checks retraining conditions.

    Runs an asyncio loop at a configurable interval. Each cycle:
      1. Checks if the training dataset has grown enough
      2. If triggered: trains candidate, benchmarks, promotes if better
    """

    def __init__(
        self,
        interval_seconds: int = 300,
        retrain_min_growth_pct: float = 10.0,
    ) -> None:
        self._interval = interval_seconds
        self._growth_detector = DatasetGrowthDetector(min_growth_pct=retrain_min_growth_pct)
        self._orchestrator = RetrainingOrchestrator()
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_train_count = 0

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("scheduler started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("scheduler stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self._cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("scheduler cycle failed: %s", e)
            await asyncio.sleep(self._interval)

    async def _cycle(self) -> None:
        """Run one scheduler cycle."""
        interactions = load_user_interactions()
        if not interactions:
            return

        dataset = TrainingDataset([ui.to_training_example() for ui in interactions])
        dataset = dataset.deduplicate()
        current_size = len(dataset)

        if not self._growth_detector.should_retrain(current_size, self._last_train_count):
            logger.debug(
                "scheduler: growth below threshold (%d < %d + %.0f%%)",
                current_size, self._last_train_count, self._growth_detector.min_growth_pct,
            )
            return

        logger.info(
            "scheduler: dataset grew %d -> %d, triggering retrain",
            self._last_train_count, current_size,
        )

        model_types = ["intent_classifier", "tool_selector", "intent_router", "error_recovery", "planning", "memory_retrieval"]
        for model_type in model_types:
            try:
                result = await asyncio.to_thread(
                    self._orchestrator.promote_if_better, dataset, model_type
                )
                if result.success and result.promoted:
                    logger.info("scheduler: promoted %s v%s", model_type, result.metadata.version)
            except Exception as e:
                logger.warning("scheduler: %s retrain failed: %s", model_type, e)

        self._last_train_count = current_size
