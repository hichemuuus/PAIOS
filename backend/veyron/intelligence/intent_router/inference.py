"""Inference API for the intent router micro-model.

Provides ``route_request()`` as the primary entrypoint. Uses per-field
confidence thresholds to decide which predictions to trust:

  - mode confidence >= 0.65   → use model prediction
  - domain confidence >= 0.50 → use model prediction
  - intent confidence >= 0.50 → use model prediction

Fields below threshold are marked for heuristic fallback by the caller.
Returns ``requires_llm=True`` if too many fields are uncertain.
"""

from __future__ import annotations

import logging
from pathlib import Path

from veyron.intelligence.intent_router.model import IntentRouterModel
from veyron.intelligence.intent_router.schema import (
    DOMAIN_THRESHOLD,
    INTENT_THRESHOLD,
    MODE_THRESHOLD,
    IntentRouterPrediction,
)

logger = logging.getLogger(__name__)

_model: IntentRouterModel | None = None
_model_path: str | None = None


def _default_model_path() -> str:
    from veyron.config import DATA_DIR
    return str(DATA_DIR / "models" / "intent_router.pkl")


def _load_model() -> IntentRouterModel | None:
    global _model
    if _model is not None:
        return _model

    path = _model_path or _default_model_path()
    model_file = Path(path)
    if not model_file.exists():
        logger.info("no intent router model found at %s", model_file)
        return None

    try:
        model = IntentRouterModel()
        model.load(str(model_file))
        _model = model
        logger.info("intent router model loaded from %s", path)
        return model
    except Exception as e:
        logger.warning("failed to load intent router model: %s", e)
        return None


def route_request(
    request: str,
    model_path: str | None = None,
) -> IntentRouterPrediction:
    """Route a user request through the trained model with per-field fallback.

    Args:
        request: The user's request text.
        model_path: Optional custom path to a trained model pickle.

    Returns:
        IntentRouterPrediction with per-field predictions and confidences.
        ``requires_llm`` is True when the model is unavailable or confidence
        is too low across multiple fields.
    """
    global _model_path
    if model_path is not None:
        _model_path = model_path

    if not request or not request.strip():
        return IntentRouterPrediction(
            request=request,
            requires_llm=True,
            fallback_fields=["mode", "domain", "intent_category"],
        )

    model = _load_model()
    if model is None or not model.fitted:
        return IntentRouterPrediction(
            request=request,
            requires_llm=True,
            fallback_fields=["mode", "domain", "intent_category"],
        )

    confidences = model.predict_with_confidence(request)

    mode_pred, mode_conf = confidences.get("mode", ("react", 0.0))
    domain_pred, domain_conf = confidences.get("domain", ("general", 0.0))
    intent_pred, intent_conf = confidences.get("intent_category", ("conversation", 0.0))

    fallback_fields: list[str] = []
    if mode_conf < MODE_THRESHOLD:
        fallback_fields.append("mode")
    if domain_conf < DOMAIN_THRESHOLD:
        fallback_fields.append("domain")
    if intent_conf < INTENT_THRESHOLD:
        fallback_fields.append("intent_category")

    requires_llm = len(fallback_fields) >= 2 or (
        len(fallback_fields) == 1 and mode_conf < MODE_THRESHOLD
    )

    return IntentRouterPrediction(
        request=request,
        mode=mode_pred,
        mode_confidence=mode_conf,
        domain=domain_pred,
        domain_confidence=domain_conf,
        intent_category=intent_pred,
        intent_confidence=intent_conf,
        requires_llm=requires_llm,
        fallback_fields=fallback_fields,
    )


def reset_model() -> None:
    """Clear the cached model (primarily for tests)."""
    global _model, _model_path
    _model = None
    _model_path = None
