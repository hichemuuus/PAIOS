"""Intelligence layer — routes requests through micro-models before falling back to the LLM.

Phase 12.2: intent router micro-model added as an optional first decision layer.
The intent router predicts mode/domain/intent_category with per-field confidence
fallback. Only uncertain fields fall through to the intent classifier, then to
the heuristic router, then to the LLM.

Flow:
  1. If micro_models_enabled, run intent router (fast path).
  2. Per-field: if model confidence >= threshold, use model prediction.
     Uncertain fields are filled by the intent classifier (if available)
     or the heuristic router.
  3. Tool selector runs on the combined predictions.
  4. If overall confidence is insufficient, fall through to heuristic router.
  5. Heuristic router is the final fallback (never disabled).
"""

from __future__ import annotations

import logging

from veyron.config import get_settings
from veyron.intelligence.intent.dataset import CATEGORY_TO_DOMAIN, CATEGORY_TO_MODE
from veyron.intelligence.intent.inference import (
    ClassifierResult,
    classify_intent,
)
from veyron.intelligence.intent_router.inference import route_request as model_route_request
from veyron.intelligence.tool_selector.inference import predict_tool_names
from veyron.llm.micro.router import Intent
from veyron.llm.micro.router import route as heuristic_route

logger = logging.getLogger(__name__)


def _classifier_to_intent(result: ClassifierResult, predicted_tools: list[str] | None = None) -> Intent:
    """Convert a ClassifierResult to the canonical Intent dataclass."""
    mode = CATEGORY_TO_MODE.get(result.category, "react")
    domain = CATEGORY_TO_DOMAIN.get(result.category, "general")

    if result.requires_planning or result.complexity == "complex":
        mode = "plan"

    return Intent(
        mode=mode,
        domain=domain,
        confidence=result.confidence,
        intent_category=result.category,
        predicted_tools=predicted_tools or result.all_probabilities.get("predicted_tools"),
    )


def _merge_predictions(
    model_pred, classifier_result, request: str
) -> tuple[str, str, str, float, list[str]]:
    """Merge model predictions with classifier fallback per field.

    Returns (mode, domain, intent_category, overall_confidence, fallback_fields).
    """
    mode = model_pred.mode
    domain = model_pred.domain
    intent_cat = model_pred.intent_category
    fallback_fields = list(model_pred.fallback_fields)

    # Fill fallback fields from classifier.
    if "mode" in fallback_fields:
        mode = CATEGORY_TO_MODE.get(classifier_result.category, "react")
        if classifier_result.requires_planning or classifier_result.complexity == "complex":
            mode = "plan"
    if "domain" in fallback_fields:
        domain = CATEGORY_TO_DOMAIN.get(classifier_result.category, "general")
    if "intent_category" in fallback_fields:
        intent_cat = classifier_result.category

    # Overall confidence: lowest of the three non-fallback fields.
    confidences = []
    if "mode" not in fallback_fields:
        confidences.append(model_pred.mode_confidence)
    if "domain" not in fallback_fields:
        confidences.append(model_pred.domain_confidence)
    if "intent_category" not in fallback_fields:
        confidences.append(model_pred.intent_confidence)
    overall_conf = min(confidences) if confidences else classifier_result.confidence

    return mode, domain, intent_cat, overall_conf, fallback_fields


def classify_request(request: str) -> Intent:
    """Classify a user request, returning an Intent for routing.

    When micro-models are enabled:
      1. Intent router predicts mode/domain/intent with per-field confidence
      2. Low-confidence fields fall back to the intent classifier
      3. Tool selector predicts required tools
      4. If overall confidence >= threshold, use combined predictions

    When disabled, falls through to the heuristic router.

    Args:
        request: The user's natural-language request.

    Returns:
        An Intent dataclass compatible with the existing agent routing.
    """
    settings = get_settings()

    if settings.model.micro_models_enabled:
        # Step 1: Run the intent router (fast path).
        model_pred = model_route_request(request)

        # Step 2: Run the intent classifier (fallback for uncertain fields).
        classifier_result = classify_intent(request)

        # Step 3: Merge per-field predictions.
        mode, domain, intent_cat, overall_conf, fallback_fields = _merge_predictions(
            model_pred, classifier_result, request
        )

        threshold = settings.model.micro_model_confidence_threshold

        # Step 4: If still too uncertain, fall through to heuristic.
        if overall_conf < threshold and model_pred.requires_llm:
            logger.info(
                "intent router confidence too low (%.3f < %.2f) for '%s' — falling through to heuristic",
                overall_conf, threshold, request[:60],
            )
            heur = heuristic_route(request)
            # Preserve intent_category from model if it was confident.
            if "intent_category" not in fallback_fields:
                heur.intent_category = intent_cat
            return heur

        # Step 5: Run tool selector.
        predicted_tools: list[str] | None = None
        try:
            tool_preds = predict_tool_names(request)
            if tool_preds:
                predicted_tools = tool_preds
        except Exception:
            logger.debug("tool selector unavailable", exc_info=True)

        logger.debug(
            "intent router: mode=%s (%.3f), domain=%s (%.3f), intent=%s (%.3f) "
            "fallback=%s tools=%s",
            mode, model_pred.mode_confidence,
            domain, model_pred.domain_confidence,
            intent_cat, model_pred.intent_confidence,
            fallback_fields, predicted_tools,
        )

        return Intent(
            mode=mode,
            domain=domain,
            confidence=overall_conf,
            intent_category=intent_cat,
            predicted_tools=predicted_tools,
        )

    return heuristic_route(request)
