"""Inference API for the tool selector micro-model.

Provides `predict_tools()` as the primary entrypoint. The function:
  1. Loads the model (lazily, on first call)
  2. Runs inference
  3. Returns ordered tool predictions with confidence scores

Falls back to an empty list if no trained model is available.
"""

from __future__ import annotations

import logging
from pathlib import Path

from veyron.config import DATA_DIR
from veyron.intelligence.tool_selector.model import ToolSelectorModel
from veyron.intelligence.tool_selector.schema import ToolPrediction

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = DATA_DIR / "models" / "tool_selector.pkl"

_model: ToolSelectorModel | None = None
_model_path: str | None = None


def _load_model() -> ToolSelectorModel | None:
    global _model
    if _model is not None:
        return _model

    path = _model_path or str(DEFAULT_MODEL_PATH)
    model_path = Path(path)
    if not model_path.exists():
        logger.info("no tool selector model found at %s", model_path)
        return None

    try:
        model = ToolSelectorModel()
        model.load(str(model_path))
        _model = model
        logger.info("tool selector model loaded from %s", path)
        return model
    except Exception as e:
        logger.warning("failed to load tool selector model: %s", e)
        return None


def predict_tools(
    text: str,
    top_k: int | None = None,
    model_path: str | None = None,
) -> list[ToolPrediction]:
    """Predict required tools for a user request.

    Args:
        text: The user's request text.
        top_k: If set, returns only the top-k predictions.
        model_path: Optional path to a trained model pickle.

    Returns:
        Ordered list of ToolPrediction with confidence scores.
        Empty list if no model is available.
    """
    global _model_path
    if model_path is not None:
        _model_path = model_path

    model = _load_model()
    if model is not None and model.fitted:
        if top_k is not None:
            return model.predict_top_k(text, k=top_k)
        return model.predict_with_confidence(text)

    return []


def predict_tool_names(
    text: str,
    confidence_threshold: float | None = None,
    model_path: str | None = None,
) -> list[str]:
    """Predict required tool names (strings only) for a user request.

    Args:
        text: The user's request text.
        confidence_threshold: Override the model's default threshold.
        model_path: Optional path to a trained model pickle.

    Returns:
        List of tool names above the confidence threshold.
        Empty list if no model is available.
    """
    global _model_path
    if model_path is not None:
        _model_path = model_path
    model = _load_model()
    if model is not None and model.fitted:
        if confidence_threshold is not None:
            old = model._confidence_threshold
            model._confidence_threshold = confidence_threshold
            result = model.predict(text)
            model._confidence_threshold = old
            return result
        return model.predict(text)
    return []


def reset_model() -> None:
    global _model, _model_path
    _model = None
    _model_path = None
