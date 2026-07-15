from __future__ import annotations

import tempfile
from pathlib import Path

from veyron.intelligence.error_recovery.dataset import ErrorRecoveryDataset
from veyron.intelligence.error_recovery.evaluation import ErrorRecoveryEvaluator
from veyron.intelligence.error_recovery.inference import (
    predict_recovery_action,
    reset_model,
)
from veyron.intelligence.error_recovery.model import ErrorRecoveryModel
from veyron.intelligence.error_recovery.schema import (
    RECOVERY_CONFIDENCE_THRESHOLD,
    ErrorRecoveryExample,
    RecoveryAction,
)
from veyron.intelligence.error_recovery.trainer import train_error_recovery


class TestErrorRecoveryModel:
    def test_fit_and_predict(self):
        model = ErrorRecoveryModel()
        texts = [
            "timeout reading file | tool: filesystem_read | context: file operation | previous: none",
            "permission denied | tool: terminal | context: tool execution | previous: retry",
            "invalid input | tool: system_monitor | context: system management | previous: none",
        ]
        labels = ["retry", "clarify", "clarify"]
        model.fit(texts, labels)
        assert model.fitted

    def test_predict_proba_returns_all_categories(self):
        model = ErrorRecoveryModel()
        texts = [
            "timeout | tool: filesystem_read | context: file | previous: none",
            "permission | tool: terminal | context: exec | previous: retry",
            "invalid | tool: system_monitor | context: mgmt | previous: none",
            "not found | tool: project_analyzer | context: analysis | previous: alt",
            "OOM | tool: terminal | context: coding | previous: none",
            "clarify | tool: terminal | context: exec | previous: fallback_llm",
        ]
        labels = ["retry", "clarify", "clarify", "modify_parameters", "fallback_llm", "alternative_tool"]
        model.fit(texts, labels)
        probs = model.predict_proba("timeout reading file")
        all_actions = {a.value for a in RecoveryAction}
        assert set(probs.keys()) == all_actions
        assert abs(sum(probs.values()) - 1.0) < 0.01

    def test_predict_with_confidence(self):
        model = ErrorRecoveryModel()
        texts = [
            "timeout | tool: filesystem_read | context: file | previous: none",
            "permission denied | tool: terminal | context: exec | previous: retry",
        ]
        labels = ["retry", "clarify"]
        model.fit(texts, labels)
        action, conf = model.predict_with_confidence("timeout | tool: filesystem_read | context: file | previous: none")
        assert action == "retry"
        assert 0.0 <= conf <= 1.0

    def test_not_fitted_fallback(self):
        model = ErrorRecoveryModel()
        assert model.predict("anything") == RecoveryAction.FALLBACK_LLM.value
        action, conf = model.predict_with_confidence("anything")
        assert action == RecoveryAction.FALLBACK_LLM.value
        assert conf == 0.0
        probs = model.predict_proba("anything")
        assert all(v == 0.0 for v in probs.values())

    def test_save_and_load(self):
        model = ErrorRecoveryModel()
        texts = [
            "timeout | tool: filesystem_read | context: file | previous: none",
            "permission denied | tool: terminal | context: exec | previous: retry",
        ]
        labels = ["retry", "clarify"]
        model.fit(texts, labels)
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = f.name
        try:
            model.save(path)
            loaded = ErrorRecoveryModel()
            loaded.load(path)
            assert loaded.fitted
            assert loaded.predict("timeout | tool: filesystem_read | context: file | previous: none") == "retry"
        finally:
            Path(path).unlink(missing_ok=True)


class TestErrorRecoveryDataset:
    def test_generate_synthetic(self):
        dataset = ErrorRecoveryDataset()
        examples = [
            ErrorRecoveryExample(
                error_message="timeout reading file",
                tool_name="filesystem_read",
                task_context="file operation",
                previous_action="none",
                recovery_action=RecoveryAction.RETRY,
            ),
            ErrorRecoveryExample(
                error_message="permission denied",
                tool_name="terminal",
                task_context="tool execution",
                previous_action="retry",
                recovery_action=RecoveryAction.CLARIFY,
            ),
        ]
        for ex in examples:
            dataset.add(ex)
        assert len(dataset) == 2
        assert dataset[1].recovery_action == RecoveryAction.CLARIFY

    def test_stratified_split(self):
        examples = []
        actions = [RecoveryAction.RETRY, RecoveryAction.CLARIFY, RecoveryAction.MODIFY_PARAMETERS]
        for i, a in enumerate(actions):
            for _ in range(10):
                examples.append(ErrorRecoveryExample(
                    error_message=f"error {i}",
                    tool_name="terminal",
                    task_context="test",
                    previous_action="none",
                    recovery_action=a,
                ))
        dataset = ErrorRecoveryDataset(examples)
        train, test = dataset.stratified_split(test_ratio=0.3, seed=42)
        assert len(train) > 0
        assert len(test) > 0
        assert len(train) + len(test) == len(dataset)

    def test_from_jsonl_and_to_jsonl(self):
        dataset = ErrorRecoveryDataset()
        dataset.add(ErrorRecoveryExample(
            error_message="timeout",
            tool_name="filesystem_read",
            task_context="file operation",
            previous_action="none",
            recovery_action=RecoveryAction.RETRY,
        ))
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False, encoding="utf-8") as f:
            path = f.name
            dataset.to_jsonl(path)
        try:
            loaded = ErrorRecoveryDataset.from_jsonl(path)
            assert len(loaded) == 1
            assert loaded[0].recovery_action == RecoveryAction.RETRY
            assert loaded[0].tool_name == "filesystem_read"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_texts_and_labels(self):
        dataset = ErrorRecoveryDataset()
        dataset.add(ErrorRecoveryExample(
            error_message="timeout reading file",
            tool_name="filesystem_read",
            task_context="file operation",
            previous_action="none",
            recovery_action=RecoveryAction.RETRY,
        ))
        assert len(dataset.texts()) == 1
        assert "timeout reading file" in dataset.texts()[0]
        assert dataset.labels() == ["retry"]

    def test_summary(self):
        dataset = ErrorRecoveryDataset()
        dataset.add(ErrorRecoveryExample(
            error_message="timeout",
            tool_name="filesystem_read",
            task_context="file operation",
            previous_action="none",
            recovery_action=RecoveryAction.RETRY,
        ))
        summary = dataset.summary()
        assert summary["total"] == 1
        assert summary["action_distribution"]["retry"] == 1


class TestErrorRecoveryInference:
    def test_empty_error_message_falls_back(self):
        reset_model()
        result = predict_recovery_action("", "filesystem_read")
        assert result.recovery_action == RecoveryAction.FALLBACK_LLM
        assert result.fallback is True
        assert result.requires_llm is True

    def test_no_model_file_falls_back(self, isolated_data_dir):
        reset_model()
        result = predict_recovery_action("timeout reading file", "filesystem_read")
        assert result.recovery_action == RecoveryAction.FALLBACK_LLM
        assert result.fallback is True

    def test_with_loaded_model(self, isolated_data_dir):
        reset_model()
        model = ErrorRecoveryModel()
        texts = [
            "timeout | tool: filesystem_read | context: file operation | previous: none",
            "permission denied | tool: terminal | context: tool execution | previous: retry",
        ]
        labels = ["retry", "clarify"]
        model.fit(texts, labels)
        model_path = str(isolated_data_dir / "models" / "error_recovery.pkl")
        model.save(model_path)

        result = predict_recovery_action(
            "timeout reading file",
            "filesystem_read",
            task_context="file operation",
            model_path=model_path,
        )
        assert result.recovery_action == RecoveryAction.RETRY
        assert result.confidence >= RECOVERY_CONFIDENCE_THRESHOLD
        assert result.fallback is False
        reset_model()

    def test_model_cache_respected(self, isolated_data_dir):
        reset_model()
        model = ErrorRecoveryModel()
        model.fit(
            ["timeout | tool: fs | context: op | previous: none", "permission | tool: term | context: exec | previous: retry"],
            ["retry", "clarify"],
        )
        model_path = str(isolated_data_dir / "models" / "error_recovery.pkl")
        model.save(model_path)

        result1 = predict_recovery_action("timeout", "fs", model_path=model_path)
        result2 = predict_recovery_action("timeout", "fs", model_path=model_path)
        assert result1.recovery_action == result2.recovery_action
        reset_model()


class TestErrorRecoveryTraining:
    def test_train_error_recovery_small(self, isolated_data_dir):
        reset_model()
        examples = [
            ErrorRecoveryExample("timeout reading file", "filesystem_read", "file operation", "none", RecoveryAction.RETRY),
            ErrorRecoveryExample("permission denied", "terminal", "tool execution", "retry", RecoveryAction.CLARIFY),
            ErrorRecoveryExample("invalid input on path", "filesystem_write", "file operation", "none", RecoveryAction.CLARIFY),
            ErrorRecoveryExample("command not found", "terminal", "tool execution", "none", RecoveryAction.ALTERNATIVE_TOOL),
            ErrorRecoveryExample("OOM analyzing project", "project_analyzer", "project analysis", "modify_parameters", RecoveryAction.MODIFY_PARAMETERS),
            ErrorRecoveryExample("segfault during read", "filesystem_read", "file operation", "retry", RecoveryAction.RETRY),
            ErrorRecoveryExample("connection refused", "terminal", "tool execution", "none", RecoveryAction.RETRY),
            ErrorRecoveryExample("disk full writing file", "filesystem_write", "file operation", "none", RecoveryAction.FALLBACK_LLM),
            ErrorRecoveryExample("syntax error in query", "system_monitor", "system management", "none", RecoveryAction.CLARIFY),
            ErrorRecoveryExample("analyzer crashed OOM", "project_analyzer", "project analysis", "none", RecoveryAction.MODIFY_PARAMETERS),
            ErrorRecoveryExample("alternative tool needed", "terminal", "debugging", "retry", RecoveryAction.ALTERNATIVE_TOOL),
            ErrorRecoveryExample("fallback after timeout", "filesystem_read", "file operation", "modify_parameters", RecoveryAction.FALLBACK_LLM),
        ]
        dataset = ErrorRecoveryDataset(examples)

        model, metrics = train_error_recovery(
            dataset=dataset,
            output_dir=str(isolated_data_dir / "models"),
            test_ratio=0.3,
        )
        assert model.fitted
        assert "accuracy" in metrics
        assert "per_class" in metrics
        assert "model_path" in metrics
        assert Path(metrics["model_path"]).exists()


class TestErrorRecoveryEvaluator:
    def test_evaluate_model(self):
        model = ErrorRecoveryModel()
        texts = [
            "timeout | tool: filesystem_read | context: file | previous: none",
            "permission | tool: terminal | context: exec | previous: retry",
            "invalid | tool: filesystem_write | context: file | previous: none",
            "not found | tool: terminal | context: exec | previous: none",
        ]
        labels = ["retry", "clarify", "clarify", "alternative_tool"]
        model.fit(texts, labels)
        evaluator = ErrorRecoveryEvaluator()

        test_cases = [
            {"error_message": "timeout", "tool_name": "filesystem_read", "task_context": "file", "previous_action": "none", "recovery_action": "retry"},
            {"error_message": "permission", "tool_name": "terminal", "task_context": "exec", "previous_action": "retry", "recovery_action": "clarify"},
        ]
        metrics = evaluator.evaluate_model(model, test_cases)
        assert metrics["available"] is True
        assert metrics["total"] == 2
        assert "accuracy" in metrics
        assert "per_class" in metrics
        assert "confusion_matrix" in metrics

    def test_evaluate_unfitted_model(self):
        model = ErrorRecoveryModel()
        evaluator = ErrorRecoveryEvaluator()
        metrics = evaluator.evaluate_model(model, [])
        assert metrics["available"] is False
