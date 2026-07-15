from __future__ import annotations

import tempfile
from pathlib import Path

from veyron.intelligence.planning.dataset import PlanningDataset, PlanningExample
from veyron.intelligence.planning.evaluation import PlanningEvaluator
from veyron.intelligence.planning.inference import predict_plan, reset_model
from veyron.intelligence.planning.model import PlanningModel
from veyron.intelligence.planning.schema import (
    PLANNING_CONFIDENCE_THRESHOLD,
    PLANNING_STEP_CATEGORIES,
)


class TestPlanningModel:
    def test_fit_and_predict(self):
        model = PlanningModel()
        texts = [
            "what time is it | intent: conversation | complexity: simple",
            "analyze project and generate report | intent: project_analysis | complexity: complex",
            "write a script to process files | intent: coding_task | complexity: moderate",
        ]
        plan_labels = [False, True, True]
        steps_labels = ["none", "several", "few"]
        cat_matrix = [
            [0, 0, 0, 0, 0, 0, 0, 0],
            [1, 1, 1, 0, 0, 0, 1, 0],
            [0, 0, 1, 1, 0, 0, 0, 0],
        ]
        model.fit(texts, plan_labels, steps_labels, cat_matrix)
        assert model.fitted

    def test_predict_plan(self):
        model = PlanningModel()
        texts = [
            "what time is it | intent: conversation | complexity: simple",
            "tell me a joke | intent: conversation | complexity: simple",
            "list files here | intent: file_operation | complexity: simple",
            "check cpu usage | intent: system_management | complexity: simple",
            "analyze project and generate report | intent: project_analysis | complexity: complex",
            "write a script to process files | intent: coding_task | complexity: moderate",
        ]
        plan_labels = [False, False, False, False, True, True]
        steps_labels = ["none", "none", "none", "none", "several", "few"]
        cat_matrix = [
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [1, 1, 1, 0, 0, 0, 1, 0],
            [0, 0, 1, 1, 0, 0, 0, 0],
        ]
        model.fit(texts, plan_labels, steps_labels, cat_matrix)
        plan, steps, cats, plan_conf, steps_conf, overall = model.predict(
            "what time is it | intent: conversation | complexity: simple"
        )
        assert plan is False

    def test_predict_plan_proba(self):
        model = PlanningModel()
        texts = [
            "what time is it | intent: conversation | complexity: simple",
            "analyze project | intent: project_analysis | complexity: complex",
            "write a script | intent: coding_task | complexity: moderate",
        ]
        plan_labels = [False, True, True]
        steps_labels = ["none", "several", "few"]
        cat_matrix = [
            [0, 0, 0, 0, 0, 0, 0, 0],
            [1, 1, 0, 0, 0, 0, 1, 0],
            [0, 0, 1, 1, 0, 0, 0, 0],
        ]
        model.fit(texts, plan_labels, steps_labels, cat_matrix)
        prob = model.predict_plan_proba("analyze project | intent: project_analysis | complexity: complex")
        assert 0.0 <= prob <= 1.0

    def test_predict_step_proba(self):
        model = PlanningModel()
        texts = [
            "what time is it | intent: conversation | complexity: simple",
            "analyze project | intent: project_analysis | complexity: complex",
            "write a script | intent: coding_task | complexity: moderate",
            "debug crashing app | intent: debugging | complexity: moderate",
        ]
        plan_labels = [False, True, True, True]
        steps_labels = ["none", "several", "few", "few"]
        cat_matrix = [
            [0] * 8,
            [1, 0, 1, 0, 1, 0, 0, 0],
            [0, 1, 1, 1, 0, 0, 0, 0],
            [1, 0, 1, 0, 0, 0, 0, 0],
        ]
        model.fit(texts, plan_labels, steps_labels, cat_matrix)
        probs = model.predict_step_proba("analyze project | intent: project_analysis | complexity: complex")
        assert isinstance(probs, dict)
        assert all(0.0 <= v <= 1.0 for v in probs.values())

    def test_predict_categories_proba(self):
        model = PlanningModel()
        texts = [
            "what time is it | intent: conversation | complexity: simple",
            "analyze project | intent: project_analysis | complexity: complex",
            "write a script | intent: coding_task | complexity: moderate",
        ]
        plan_labels = [False, True, True]
        steps_labels = ["none", "several", "few"]
        cat_matrix = [
            [0] * 8,
            [1, 0, 0, 0, 0, 0, 1, 0],
            [0, 0, 1, 1, 0, 0, 0, 0],
        ]
        model.fit(texts, plan_labels, steps_labels, cat_matrix)
        probs = model.predict_categories_proba("analyze project")
        assert set(probs.keys()) == set(PLANNING_STEP_CATEGORIES)
        assert all(0.0 <= v <= 1.0 for v in probs.values())

    def test_save_and_load(self):
        model = PlanningModel()
        texts = [
            "what time is it | intent: conversation | complexity: simple",
            "analyze project | intent: project_analysis | complexity: complex",
        ]
        plan_labels = [False, True]
        steps_labels = ["none", "several"]
        cat_matrix = [[0] * 8, [1, 0, 0, 0, 0, 0, 1, 0]]
        model.fit(texts, plan_labels, steps_labels, cat_matrix)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = f.name
        try:
            model.save(path)
            loaded = PlanningModel()
            loaded.load(path)
            assert loaded.fitted
            plan, steps, cats, _, _, _ = loaded.predict(
                "what time is it | intent: conversation | complexity: simple"
            )
            assert plan is False
        finally:
            Path(path).unlink(missing_ok=True)

    def test_not_fitted_returns_defaults(self):
        model = PlanningModel()
        plan, steps, cats, plan_conf, steps_conf, overall = model.predict("anything")
        assert plan is False
        assert steps == 0
        assert cats == []
        assert plan_conf == 0.0
        assert steps_conf == 0.0
        assert overall == 0.0


class TestPlanningDataset:
    def test_add_and_len(self):
        dataset = PlanningDataset()
        dataset.add(PlanningExample(
            request="what time is it",
            intent_category="conversation",
            complexity="simple",
            requires_plan=False,
            estimated_steps=0,
        ))
        assert len(dataset) == 1

    def test_stratified_split(self):
        examples = [
            PlanningExample("hello", "conversation", "simple", False, 0),
            PlanningExample("world", "conversation", "simple", False, 0),
            PlanningExample("analyze project", "project_analysis", "complex", True, 5),
            PlanningExample("build app", "coding_task", "complex", True, 4),
            PlanningExample("debug crash", "debugging", "moderate", True, 3),
            PlanningExample("write script", "coding_task", "moderate", True, 3),
            PlanningExample("list files", "file_operation", "simple", False, 0),
            PlanningExample("check cpu", "system_management", "simple", False, 0),
            PlanningExample("research pattern", "research", "moderate", True, 4),
            PlanningExample("migrate database", "coding_task", "complex", True, 6),
        ]
        dataset = PlanningDataset(examples)
        train, test = dataset.stratified_split(test_ratio=0.3, seed=42)
        assert len(train) > 0
        assert len(test) > 0
        assert len(train) + len(test) == len(dataset)

    def test_from_jsonl_and_to_jsonl(self):
        dataset = PlanningDataset()
        dataset.add(PlanningExample(
            request="analyze project",
            intent_category="project_analysis",
            complexity="complex",
            requires_plan=True,
            estimated_steps=5,
            step_categories=["research", "project_analysis"],
        ))
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False, encoding="utf-8") as f:
            path = f.name
            dataset.to_jsonl(path)
        try:
            loaded = PlanningDataset.from_jsonl(path)
            assert len(loaded) == 1
            assert loaded[0].requires_plan is True
            assert loaded[0].estimated_steps == 5
        finally:
            Path(path).unlink(missing_ok=True)

    def test_texts_and_labels(self):
        dataset = PlanningDataset()
        dataset.add(PlanningExample(
            request="analyze project",
            intent_category="project_analysis",
            complexity="complex",
            requires_plan=True,
            estimated_steps=5,
            step_categories=["research", "project_analysis"],
        ))
        texts = dataset.texts()
        assert len(texts) == 1
        assert "analyze project" in texts[0]
        assert dataset.plan_labels() == [True]
        assert dataset.steps_labels() == ["several"]

    def test_summary(self):
        dataset = PlanningDataset()
        dataset.add(PlanningExample("hello", "conversation", "simple", False, 0))
        dataset.add(PlanningExample("analyze", "project_analysis", "complex", True, 5))
        summary = dataset.summary()
        assert summary["total"] == 2
        assert summary["requires_plan"] == 1
        assert summary["no_plan"] == 1


class TestPlanningInference:
    def test_empty_request_falls_back(self):
        reset_model()
        result = predict_plan("", "conversation", "simple")
        assert result.requires_plan is False
        assert result.fallback is True
        assert result.requires_llm is True

    def test_no_model_file_falls_back(self, isolated_data_dir):
        reset_model()
        result = predict_plan("analyze project", "project_analysis", "complex")
        assert result.fallback is True

    def test_with_loaded_model(self, isolated_data_dir):
        reset_model()
        model = PlanningModel()
        texts = [
            "what time is it | intent: conversation | complexity: simple",
            "analyze project and generate report | intent: project_analysis | complexity: complex",
            "write a python script | intent: coding_task | complexity: moderate",
        ]
        plan_labels = [False, True, True]
        steps_labels = ["none", "several", "few"]
        cat_matrix = [
            [0] * 8,
            [1, 0, 0, 0, 0, 0, 1, 0],
            [0, 0, 1, 1, 0, 0, 0, 0],
        ]
        model.fit(texts, plan_labels, steps_labels, cat_matrix)
        model_path = str(isolated_data_dir / "models" / "planning.pkl")
        model.save(model_path)

        result = predict_plan(
            "analyze project and generate report",
            "project_analysis",
            "complex",
            model_path=model_path,
        )
        assert result.requires_plan is True
        assert result.confidence >= PLANNING_CONFIDENCE_THRESHOLD
        assert result.fallback is False
        reset_model()

    def test_model_cache_respected(self, isolated_data_dir):
        reset_model()
        model = PlanningModel()
        texts = [
            "simple query | intent: conversation | complexity: simple",
            "complex task | intent: project_analysis | complexity: complex",
        ]
        plan_labels = [False, True]
        steps_labels = ["none", "several"]
        cat_matrix = [[0] * 8, [1, 0, 0, 0, 0, 0, 1, 0]]
        model.fit(texts, plan_labels, steps_labels, cat_matrix)
        model_path = str(isolated_data_dir / "models" / "planning.pkl")
        model.save(model_path)

        result1 = predict_plan("simple query", "conversation", "simple", model_path=model_path)
        result2 = predict_plan("simple query", "conversation", "simple", model_path=model_path)
        assert result1.requires_plan == result2.requires_plan
        reset_model()


class TestPlanningTraining:
    def test_train_planning_small(self, isolated_data_dir):
        reset_model()
        examples = [
            PlanningExample("hello", "conversation", "simple", False, 0),
            PlanningExample("analyze project", "project_analysis", "complex", True, 5, ["research", "project_analysis"]),
            PlanningExample("write script", "coding_task", "moderate", True, 3, ["coding_task", "debugging"]),
            PlanningExample("list files", "file_operation", "simple", False, 0),
            PlanningExample("debug crash", "debugging", "moderate", True, 3, ["debugging", "tool_execution"]),
            PlanningExample("check cpu", "system_management", "simple", False, 0),
            PlanningExample("build web app", "coding_task", "complex", True, 6, ["coding_task", "tool_execution"]),
            PlanningExample("research patterns", "research", "moderate", True, 4, ["research", "question_answering"]),
            PlanningExample("migrate database", "coding_task", "complex", True, 6, ["research", "coding_task"]),
            PlanningExample("set up ci cd", "system_management", "complex", True, 5, ["research", "tool_execution"]),
        ]
        dataset = PlanningDataset(examples)

        from veyron.intelligence.planning.trainer import train_planning
        model, metrics = train_planning(
            dataset=dataset,
            output_dir=str(isolated_data_dir / "models"),
            test_ratio=0.3,
        )
        assert model.fitted
        assert "plan_accuracy" in metrics
        assert "steps_accuracy" in metrics
        assert "model_path" in metrics
        assert Path(metrics["model_path"]).exists()


class TestPlanningEvaluator:
    def test_evaluate_model(self):
        model = PlanningModel()
        texts = [
            "hello | intent: conversation | complexity: simple",
            "analyze project | intent: project_analysis | complexity: complex",
            "write script | intent: coding_task | complexity: moderate",
            "list files | intent: file_operation | complexity: simple",
        ]
        plan_labels = [False, True, True, False]
        steps_labels = ["none", "several", "few", "none"]
        cat_matrix = [
            [0] * 8,
            [1, 0, 0, 0, 0, 0, 1, 0],
            [0, 0, 1, 1, 0, 0, 0, 0],
            [0] * 8,
        ]
        model.fit(texts, plan_labels, steps_labels, cat_matrix)

        examples = [
            PlanningExample("hello", "conversation", "simple", False, 0),
            PlanningExample("analyze project", "project_analysis", "complex", True, 5),
        ]
        dataset = PlanningDataset(examples)

        evaluator = PlanningEvaluator()
        metrics = evaluator.evaluate_model(model, dataset)
        assert metrics["available"] is True
        assert metrics["total"] == 2
        assert "plan_accuracy" in metrics
        assert "steps_accuracy" in metrics
        assert "mean_category_jaccard" in metrics

    def test_evaluate_unfitted_model(self):
        model = PlanningModel()
        evaluator = PlanningEvaluator()
        dataset = PlanningDataset()
        metrics = evaluator.evaluate_model(model, dataset)
        assert metrics["available"] is False
