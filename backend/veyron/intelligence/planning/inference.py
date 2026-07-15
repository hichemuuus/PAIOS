from __future__ import annotations

import logging
from pathlib import Path

from veyron.intelligence.planning.model import PlanningModel
from veyron.intelligence.planning.schema import (
    PLANNING_CONFIDENCE_THRESHOLD,
    PlanningPrediction,
)

logger = logging.getLogger(__name__)

_model: PlanningModel | None = None
_model_path: str | None = None


def _default_model_path() -> str:
    from veyron.config import DATA_DIR

    return str(DATA_DIR / "models" / "planning.pkl")


def _load_model() -> PlanningModel | None:
    global _model
    if _model is not None:
        return _model

    path = _model_path or _default_model_path()
    model_file = Path(path)
    if not model_file.exists():
        logger.info("no planning model found at %s", model_file)
        return None

    try:
        model = PlanningModel()
        model.load(str(model_file))
        _model = model
        logger.info("planning model loaded from %s", path)
        return model
    except Exception as e:
        logger.warning("failed to load planning model: %s", e)
        return None


def _build_text(
    request: str,
    intent_category: str = "",
    complexity: str = "",
) -> str:
    return f"{request} | intent: {intent_category or 'general'} | complexity: {complexity or 'simple'}"


def predict_plan(
    request: str,
    intent_category: str = "",
    complexity: str = "",
    model_path: str | None = None,
) -> PlanningPrediction:
    global _model_path
    if model_path is not None:
        _model_path = model_path

    if not request or not request.strip():
        return PlanningPrediction(
            request=request,
            requires_plan=False,
            estimated_steps=0,
            requires_llm=True,
            fallback=True,
        )

    model = _load_model()
    if model is None or not model.fitted:
        return PlanningPrediction(
            request=request,
            requires_plan=False,
            estimated_steps=0,
            requires_llm=True,
            fallback=True,
        )

    text = _build_text(request, intent_category, complexity)
    requires_plan, estimated_steps, step_categories, plan_conf, steps_conf, overall_conf = model.predict(text)

    requires_llm = overall_conf < PLANNING_CONFIDENCE_THRESHOLD
    fallback = overall_conf < PLANNING_CONFIDENCE_THRESHOLD

    return PlanningPrediction(
        request=request,
        requires_plan=requires_plan,
        estimated_steps=estimated_steps,
        step_categories=step_categories,
        confidence=round(overall_conf, 3),
        plan_confidence=round(plan_conf, 3),
        steps_confidence=round(steps_conf, 3),
        requires_llm=requires_llm,
        fallback=fallback,
    )


def reset_model() -> None:
    global _model, _model_path
    _model = None
    _model_path = None
