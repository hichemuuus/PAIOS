"""Training data exporter — writes collected examples as JSONL files.

Manages the output directory under DATA_DIR/training/ and provides
convenience methods for exporting training-ready datasets.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from veyron.config import DATA_DIR
from veyron.intelligence.training.dataset import TrainingDataset

logger = logging.getLogger(__name__)


class TrainingExporter:
    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else (DATA_DIR / "training")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_dataset(
        self,
        dataset: TrainingDataset,
        filename: str | None = None,
        split_ratio: float = 0.0,
    ) -> dict[str, Path]:
        if filename is None:
            ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            filename = f"training_data_{ts}.jsonl"

        if split_ratio > 0.0:
            train, test = dataset.split(split_ratio)
            stem = Path(filename).stem
            train_path = self.output_dir / f"{stem}_train.jsonl"
            test_path = self.output_dir / f"{stem}_test.jsonl"
            train.to_jsonl(train_path)
            test.to_jsonl(test_path)
            logger.info(
                "exported split dataset: %d train, %d test",
                len(train), len(test),
            )
            return {"train": train_path, "test": test_path}

        path = self.output_dir / filename
        dataset.to_jsonl(path)
        return {"dataset": path}

    def export_by_category(
        self,
        dataset: TrainingDataset,
    ) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        for category, cat_dataset in dataset.by_category().items():
            if len(cat_dataset) == 0:
                continue
            safe_name = category.replace(" ", "_").lower()
            path = self.output_dir / f"{safe_name}.jsonl"
            cat_dataset.to_jsonl(path)
            paths[category] = path
        return paths

    def export_summary(self, dataset: TrainingDataset) -> Path:
        summary = dataset.summary()
        path = self.output_dir / "dataset_summary.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info("exported dataset summary to %s", path)
        return path

    def list_exports(self) -> list[dict[str, Any]]:
        if not self.output_dir.exists():
            return []
        exports: list[dict[str, Any]] = []
        for fpath in sorted(self.output_dir.iterdir()):
            if fpath.suffix in (".jsonl", ".json"):
                exports.append({
                    "filename": fpath.name,
                    "size_bytes": fpath.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        fpath.stat().st_mtime, tz=UTC
                    ).isoformat(),
                })
        return exports


_exporter: TrainingExporter | None = None
_exporter_lock = threading.Lock()


def get_exporter(output_dir: str | Path | None = None) -> TrainingExporter:
    global _exporter
    if _exporter is None:
        with _exporter_lock:
            if _exporter is None:
                _exporter = TrainingExporter(output_dir=output_dir)
    return _exporter


def reset_exporter() -> None:
    global _exporter
    _exporter = None
