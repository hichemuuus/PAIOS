"""Inference API for the memory retrieval micro-model.

Provides ``retrieve_memories()`` as the primary entrypoint. Falls back to an
empty ranking if no trained model is available, so callers (the agent context
builder, the memory store) can always treat the result as "best effort".
"""

from __future__ import annotations

import logging
from pathlib import Path

from veyron.intelligence.memory_retrieval.model import MemoryRetrievalModel

logger = logging.getLogger(__name__)

_model: MemoryRetrievalModel | None = None
_model_path: str | None = None


def _default_model_path() -> str:
    from veyron.config import DATA_DIR
    return str(DATA_DIR / "models" / "memory_retrieval.pkl")


def _load_model() -> MemoryRetrievalModel | None:
    global _model
    if _model is not None:
        return _model

    path = _model_path or _default_model_path()
    model_path = Path(path)
    if not model_path.exists():
        logger.info("no memory retrieval model found at %s", model_path)
        return None

    try:
        model = MemoryRetrievalModel()
        model.load(str(model_path))
        _model = model
        logger.info("memory retrieval model loaded from %s", path)
        return model
    except Exception as e:
        logger.warning("failed to load memory retrieval model: %s", e)
        return None


def retrieve_memories(
    query: str,
    candidates: list[str],
    top_k: int = 5,
    model_path: str | None = None,
) -> list[int]:
    """Rank candidate memories by relevance to a query.

    Args:
        query: The user's request text.
        candidates: Candidate memory texts to rank.
        top_k: Maximum number of indices to return.
        model_path: Optional path to a trained model pickle.

    Returns:
        List of candidate indices ranked by relevance (most relevant first).
        Empty list if no model is available or the input is empty.
    """
    global _model_path
    if model_path is not None:
        _model_path = model_path

    if not candidates:
        return []

    model = _load_model()
    if model is not None and model.fitted:
        return model.predict(query, candidates, top_k=top_k)

    return []


def reset_model() -> None:
    """Clear the cached model (primarily for tests)."""
    global _model, _model_path
    _model = None
    _model_path = None
