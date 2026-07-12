"""Intelligence layer — routes requests through micro-models before falling back to the LLM.

Phase 9.4: micro-models become the first decision layer. The intent
classifier and tool selector run first at low latency. Only low-confidence
requests route to the LLM.

Flow:
  1. If micro_models_enabled, run intent classifier + tool selector.
  2. If confidence >= threshold, use micro-model predictions:
       - predicted_tools are returned for downstream schema filtering
       - Simple + no tool → direct answer (bypass LLM entirely)
       - Tool needed but no planning → ReAct loop
       - Planning needed → Planner delegation
  3. Low confidence → fall through to heuristic router.
  4. Heuristic router remains the final fallback when micro-models are disabled.
"""

from __future__ import annotations

import logging

from paios.config import get_settings
from paios.intelligence.intent.inference import (
    ClassifierResult,
    classify_intent,
    should_use_llm,
)
from paios.intelligence.intent.dataset import CATEGORY_TO_DOMAIN, CATEGORY_TO_MODE
from paios.intelligence.tool_selector.inference import predict_tool_names
from paios.llm.micro.router import Intent, route as heuristic_route

logger = logging.getLogger(__name__)


def _classifier_to_intent(result: ClassifierResult, predicted_tools: list[str] | None = None) -> Intent:
    """Convert a ClassifierResult to the canonical Intent dataclass."""
    mode = CATEGORY_TO_MODE.get(result.category, "react")
    domain = CATEGORY_TO_DOMAIN.get(result.category, "general")

    # Override mode based on complexity and planning needs.
    if result.requires_planning or result.complexity == "complex":
        mode = "plan"

    return Intent(
        mode=mode,
        domain=domain,
        confidence=result.confidence,
        intent_category=result.category,
        predicted_tools=predicted_tools or result.all_probabilities.get("predicted_tools"),
    )


def classify_request(request: str) -> Intent:
    """Classify a user request, returning an Intent for routing.

    When micro-models are enabled:
      1. Intent classifier predicts category + confidence
      2. Tool selector predicts required tools
      3. If confidence >= threshold, use predictions; otherwise fall through

    When disabled, falls through to the heuristic router (Phase 1 stand-in).

    Args:
        request: The user's natural-language request.

    Returns:
        An Intent dataclass compatible with the existing agent routing.
    """
    settings = get_settings()

    if settings.model.micro_models_enabled:
        result = classify_intent(request)

        threshold = settings.model.micro_model_confidence_threshold

        if not should_use_llm(result, threshold=threshold):
            # Run tool selector when micro-model is confident.
            predicted_tools: list[str] | None = None
            try:
                tool_preds = predict_tool_names(request)
                if tool_preds:
                    predicted_tools = tool_preds
            except Exception:
                logger.debug("tool selector unavailable, continuing without it", exc_info=True)

            logger.debug(
                "micro-model classified '%s' as '%s' (conf=%.3f, tools=%s)",
                request[:60],
                result.category,
                result.confidence,
                predicted_tools,
            )

            return _classifier_to_intent(result, predicted_tools=predicted_tools)

        logger.info(
            "micro-model confidence too low (%.3f < %.2f) for '%s' — falling through",
            result.confidence,
            threshold,
            request[:60],
        )

    return heuristic_route(request)
