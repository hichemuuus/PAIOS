"""Schema for the intent router micro-model.

The intent router predicts three outputs from a user request:
  - mode: "react" | "plan" (how to execute)
  - domain: which tool domain applies
  - intent_category: the semantic category of the request

Each prediction carries its own confidence score so callers can apply
per-field fallback thresholds independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IntentRouterExample:
    """A single training/evaluation example for the intent router.

    Attributes:
        request: The user's request text.
        mode: Ground-truth execution mode ("react" | "plan").
        domain: Ground-truth tool domain.
        intent_category: Ground-truth intent category.
        difficulty: Optional difficulty hint ("easy", "moderate", "hard").
    """
    request: str
    mode: str = "react"
    domain: str = "general"
    intent_category: str = "conversation"
    difficulty: str = "easy"


@dataclass
class IntentRouterPrediction:
    """Prediction output from the intent router model.

    Attributes:
        request: The input request text.
        mode: Predicted execution mode.
        mode_confidence: Confidence for mode prediction.
        domain: Predicted tool domain.
        domain_confidence: Confidence for domain prediction.
        intent_category: Predicted intent category.
        intent_confidence: Confidence for intent prediction.
        requires_llm: True if any field confidence is below threshold.
        fallback_fields: List of field names that fell back to heuristic.
    """
    request: str
    mode: str = "react"
    mode_confidence: float = 0.0
    domain: str = "general"
    domain_confidence: float = 0.0
    intent_category: str = "conversation"
    intent_confidence: float = 0.0
    requires_llm: bool = True
    fallback_fields: list[str] = field(default_factory=list)


# Per-field confidence thresholds for fallback decisions.
# These are conservative — the model must be reasonably sure or we fall through.
MODE_THRESHOLD = 0.65
DOMAIN_THRESHOLD = 0.50
INTENT_THRESHOLD = 0.50
