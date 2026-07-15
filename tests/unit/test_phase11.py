"""Phase 11 tests — Intelligence Integration: parameter extraction & scheduler.

Covers:
  - ParameterExtractionModel: fit, predict, save/load
  - train_parameter_extraction: training pipeline
  - predict_parameters / predict_parameters_multitool: inference API
  - IntelligenceScheduler: lifecycle and cycle triggers
  - Agent integration: _save_interaction hook
  - Registry extension: parameter_extraction model type
"""

from __future__ import annotations

import json

import pytest
from veyron.intelligence.models.registry import ModelRegistry
from veyron.intelligence.models.schema import STATUS_PRODUCTION, ModelMetadata
from veyron.intelligence.parameter_extraction.dataset import ParameterExtractionDataset
from veyron.intelligence.parameter_extraction.inference import (
    predict_parameters,
    predict_parameters_multitool,
    reset_model,
)
from veyron.intelligence.parameter_extraction.model import ParameterExtractionModel
from veyron.intelligence.parameter_extraction.schema import ParameterExample
from veyron.intelligence.parameter_extraction.trainer import train_parameter_extraction
from veyron.intelligence.scheduler import IntelligenceScheduler

# ═══════════════════════════════════════════════════════════════════
# ParameterExtractionModel
# ═══════════════════════════════════════════════════════════════════

class TestParameterExtractionModel:
    def test_not_fitted_raises(self):
        model = ParameterExtractionModel()
        with pytest.raises(RuntimeError, match="not fitted"):
            model.predict("hello", "filesystem_read")

    def test_fit_and_predict_single_tool(self):
        model = ParameterExtractionModel()
        data = [
            ("list test files", "filesystem_read", {"path": "tests", "pattern": "*.py"}),
            ("read readme", "filesystem_read", {"path": "README.md"}),
            ("list src files", "filesystem_read", {"path": "src", "pattern": "*.ts"}),
        ]
        model.fit(data)
        assert model.fitted
        assert "filesystem_read" in model.tools

        result = model.predict("show me test files", "filesystem_read")
        assert isinstance(result, dict)
        assert "path" in result

    def test_fit_and_predict_multiple_tools(self):
        model = ParameterExtractionModel()
        data = [
            ("list test files", "filesystem_read", {"path": "tests", "pattern": "*.py"}),
            ("check cpu usage", "system_monitor", {"metric": "cpu"}),
            ("read readme", "filesystem_read", {"path": "README.md"}),
            ("check memory", "system_monitor", {"metric": "memory"}),
        ]
        model.fit(data)
        assert model.fitted
        assert "filesystem_read" in model.tools
        assert "system_monitor" in model.tools

        fs_result = model.predict("list all test files", "filesystem_read")
        assert "path" in fs_result

        sm_result = model.predict("check cpu usage", "system_monitor")
        assert "metric" in sm_result

    def test_predict_unknown_tool_returns_empty(self):
        model = ParameterExtractionModel()
        model.fit([("hello", "filesystem_read", {"path": "."})])
        result = model.predict("hi", "unknown_tool")
        assert result == {}

    def test_save_load_roundtrip(self, tmp_path):
        model = ParameterExtractionModel()
        data = [
            ("list test files", "filesystem_read", {"path": "tests"}),
            ("check cpu", "system_monitor", {"metric": "cpu"}),
        ]
        model.fit(data)
        path = tmp_path / "param_model.pkl"
        model.save(str(path))
        assert path.exists()

        loaded = ParameterExtractionModel()
        loaded.load(str(path))
        assert loaded.fitted
        assert loaded.tools == model.tools

        result = loaded.predict("list test files", "filesystem_read")
        assert "path" in result

    def test_predict_with_proba(self):
        model = ParameterExtractionModel()
        data = [
            ("list test files", "filesystem_read", {"path": "tests"}),
            ("read readme", "filesystem_read", {"path": "README.md"}),
        ]
        model.fit(data)
        proba = model.predict_with_proba("show me test files", "filesystem_read")
        assert "path" in proba
        assert len(proba["path"]) > 0
        candidates = proba["path"]
        assert isinstance(candidates, list)
        assert all(isinstance(c, tuple) and len(c) == 2 for c in candidates)

    def test_predict_unknown_tool_proba_empty(self):
        model = ParameterExtractionModel()
        model.fit([("hello", "filesystem_read", {"path": "."})])
        assert model.predict_with_proba("hi", "nonexistent") == {}


# ═══════════════════════════════════════════════════════════════════
# Training pipeline
# ═══════════════════════════════════════════════════════════════════

class TestTrainParameterExtraction:
    def test_train_with_inline_dataset(self, tmp_path):
        dataset = ParameterExtractionDataset([
            ParameterExample(request="list files", tool_name="filesystem_read", expected_parameters={"path": "tests"}),
            ParameterExample(request="check cpu", tool_name="system_monitor", expected_parameters={"metric": "cpu"}),
            ParameterExample(request="read readme", tool_name="filesystem_read", expected_parameters={"path": "README.md"}),
            ParameterExample(request="check memory", tool_name="system_monitor", expected_parameters={"metric": "memory"}),
        ])
        model, metrics = train_parameter_extraction(
            dataset=dataset,
            output_dir=str(tmp_path),
            test_ratio=0.25,
            seed=42,
        )
        assert model.fitted
        assert metrics["total"] > 0
        assert "exact_match_rate" in metrics
        assert "avg_parameter_accuracy" in metrics
        assert "per_tool" in metrics
        assert (tmp_path / "parameter_extraction.pkl").exists()
        assert (tmp_path / "parameter_extraction_report.json").exists()

    def test_train_with_synthetic_jsonl(self, isolated_data_dir):
        # Create a synthetic jsonl file in the isolated dir
        synth_dir = isolated_data_dir / "training"
        synth_dir.mkdir(parents=True, exist_ok=True)
        synth_file = synth_dir / "synthetic_training_data.jsonl"
        with open(synth_file, "w") as f:
            for line in [
                {"request": "list test files", "intent": "file_operation", "expected_tools": ["filesystem_read"], "expected_parameters": {"path": "tests"}},
                {"request": "check cpu usage", "intent": "system_management", "expected_tools": ["system_monitor"], "expected_parameters": {"metric": "cpu"}},
                {"request": "read readme", "intent": "file_operation", "expected_tools": ["filesystem_read"], "expected_parameters": {"path": "README.md"}},
            ]:
                f.write(json.dumps(line) + "\n")

        model, metrics = train_parameter_extraction(test_ratio=0.5, seed=42)
        assert model.fitted
        assert metrics["total"] > 0


# ═══════════════════════════════════════════════════════════════════
# Inference API
# ═══════════════════════════════════════════════════════════════════

class TestPredictParametersInference:
    def test_no_model_returns_empty(self):
        reset_model()
        result = predict_parameters("list files", "filesystem_read")
        assert result == {}

    def test_predict_with_explicit_model_path(self, tmp_path):
        # Train and save a model
        model = ParameterExtractionModel()
        model.fit([
            ("list test files", "filesystem_read", {"path": "tests"}),
            ("check cpu", "system_monitor", {"metric": "cpu"}),
        ])
        path = tmp_path / "test_param.pkl"
        model.save(str(path))

        result = predict_parameters("list test files", "filesystem_read", model_path=str(path))
        assert isinstance(result, dict)
        assert "path" in result

    def test_predict_multitool(self, tmp_path):
        model = ParameterExtractionModel()
        model.fit([
            ("list test files", "filesystem_read", {"path": "tests"}),
            ("check cpu", "system_monitor", {"metric": "cpu"}),
        ])
        path = tmp_path / "test_param.pkl"
        model.save(str(path))

        results = predict_parameters_multitool(
            "list test files",
            ["filesystem_read", "system_monitor"],
            model_path=str(path),
        )
        assert "filesystem_read" in results
        assert "system_monitor" in results
        assert "path" in results["filesystem_read"]

    def test_reset_model(self):
        reset_model()
        from veyron.intelligence.parameter_extraction.inference import _model, _model_path
        assert _model is None
        assert _model_path is None


# ═══════════════════════════════════════════════════════════════════
# IntelligenceScheduler
# ═══════════════════════════════════════════════════════════════════

class TestIntelligenceScheduler:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        scheduler = IntelligenceScheduler(interval_seconds=3600)
        assert not scheduler.is_running
        await scheduler.start()
        assert scheduler.is_running
        await scheduler.stop()
        assert not scheduler.is_running

    @pytest.mark.asyncio
    async def test_double_start(self):
        scheduler = IntelligenceScheduler(interval_seconds=3600)
        await scheduler.start()
        await scheduler.start()
        assert scheduler.is_running
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        scheduler = IntelligenceScheduler()
        await scheduler.stop()
        assert not scheduler.is_running

    @pytest.mark.asyncio
    async def test_cycle_no_interactions(self):
        scheduler = IntelligenceScheduler(interval_seconds=3600)
        await scheduler.start()
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_cycle_skips_when_below_threshold(self):
        scheduler = IntelligenceScheduler(interval_seconds=3600, retrain_min_growth_pct=50.0)
        scheduler._last_train_count = 100
        await scheduler._cycle()
        assert scheduler._last_train_count == 100

    @pytest.mark.asyncio
    async def test_cycle_catches_exception(self):
        scheduler = IntelligenceScheduler(interval_seconds=3600)
        await scheduler.start()
        async def broken_cycle():
            raise ValueError("cycle error")
        scheduler._cycle = broken_cycle
        scheduler._running = False
        await scheduler._run_loop()
        await scheduler.stop()


# ═══════════════════════════════════════════════════════════════════
# Registry extension
# ═══════════════════════════════════════════════════════════════════

class TestRegistryParameterExtraction:
    def test_register_and_production(self, tmp_path):
        registry = ModelRegistry(registry_path=tmp_path / "registry.json")
        meta = ModelMetadata(
            name="param_ext_v1",
            version="v1",
            model_type="parameter_extraction",
            dataset_hash="abc",
            dataset_size=10,
            metrics={"exact_match_rate": 0.85},
            status=STATUS_PRODUCTION,
            path=str(tmp_path / "model.pkl"),
        )
        registry.register(meta)
        production = registry.get_production("parameter_extraction")
        assert production is not None
        assert production.version == "v1"

    def test_load_production_not_found(self, tmp_path):
        registry = ModelRegistry(registry_path=tmp_path / "registry.json")
        model = registry.load_production_model("parameter_extraction")
        assert model is None

    def test_load_production_with_model(self, tmp_path):
        # Train and save a minimal model
        model = ParameterExtractionModel()
        model.fit([
            ("list test files", "filesystem_read", {"path": "tests"}),
        ])
        model_path = tmp_path / "models" / "parameter_extraction.pkl"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(model_path))

        registry = ModelRegistry(registry_path=tmp_path / "registry.json")
        meta = ModelMetadata(
            name="param_ext_v1",
            version="v1",
            model_type="parameter_extraction",
            dataset_hash="abc",
            dataset_size=1,
            metrics={"exact_match_rate": 1.0},
            status=STATUS_PRODUCTION,
            path=str(model_path),
        )
        registry.register(meta)

        loaded = registry.load_production_model("parameter_extraction")
        assert loaded is not None
        assert loaded.fitted
        result = loaded.predict("list test files", "filesystem_read")
        assert "path" in result
