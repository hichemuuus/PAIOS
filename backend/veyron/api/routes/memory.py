"""Memory API routes.

  GET    /api/memory                 — list memories (filterable, paginated)
  GET    /api/memory/search          — keyword search ranked by relevance
  GET    /api/memory/{public_id}     — single memory detail
  PATCH  /api/memory/{public_id}     — update content / importance / tags
  DELETE /api/memory/{public_id}     — delete a memory
  GET    /api/memory/stats           — aggregate counts by category

These routes expose the existing MemoryStore (veyron.memory.store) to the
frontend Memory Center. No business logic here — the store remains the
source of truth.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from veyron.db.models import MemoryCategory
from veyron.memory.store import get_memory_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])

VALID_CATEGORIES = {c.value for c in MemoryCategory}


def _serialize(mem: Any) -> dict[str, Any]:
    """Serialize a Memory row to a JSON-friendly dict."""
    cat = mem.category.value if hasattr(mem.category, "value") else str(mem.category)
    return {
        "public_id": mem.public_id,
        "category": cat,
        "content": mem.content,
        "importance": mem.importance,
        "tags": mem.tags or "",
        "created_at": mem.created_at.isoformat() if mem.created_at else None,
        "updated_at": mem.updated_at.isoformat() if mem.updated_at else None,
        "last_recalled_at": mem.last_recalled_at.isoformat() if mem.last_recalled_at else None,
        "recall_count": mem.recall_count,
        "usefulness_score": mem.usefulness_score,
        "reliability_score": mem.reliability_score,
        "success_frequency": mem.success_frequency,
        "decayed": mem.decayed,
        "source_task": mem.source_task,
    }


class MemoryUpdate(BaseModel):
    """Partial update for a memory record."""

    content: str | None = Field(default=None, min_length=1, max_length=100_000)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    tags: str | None = Field(default=None, max_length=500)


@router.get("")
def list_memories(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    category: str | None = Query(default=None),
    tags: str | None = Query(default=None),
    min_importance: float | None = Query(default=None, ge=0.0, le=1.0),
    include_decayed: bool = Query(default=False),
) -> dict[str, Any]:
    """List memories with optional filters.

    Results are ordered by importance desc, then recency desc.
    """
    if category is not None and category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"invalid category: {category}")

    store = get_memory_store()
    # The store's search() supports empty-query ranking; reuse it for listing
    # when no text query is supplied, then apply extra filters the store does
    # not expose directly.
    memories = store.search(
        query="",
        category=category,
        tags=tags,
        limit=limit + offset,  # over-fetch then slice for offset
    )

    # Apply extra filters the store does not expose directly.
    filtered: list[Any] = []
    for m in memories:
        if not include_decayed and m.decayed:
            continue
        if min_importance is not None and m.importance < min_importance:
            continue
        filtered.append(m)

    page = filtered[offset : offset + limit]
    return {
        "memories": [_serialize(m) for m in page],
        "count": len(page),
        "total": len(filtered),
        "offset": offset,
        "limit": limit,
    }


@router.get("/search")
def search_memories(
    q: str = Query(default="", max_length=500),
    category: str | None = Query(default=None),
    tags: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Keyword search over memory content, ranked by relevance."""
    if category is not None and category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"invalid category: {category}")

    store = get_memory_store()
    memories = store.search(query=q, category=category, tags=tags, limit=limit)
    return {
        "query": q,
        "memories": [_serialize(m) for m in memories],
        "count": len(memories),
    }


@router.get("/stats")
def memory_stats() -> dict[str, Any]:
    """Aggregate counts by category and importance buckets."""
    store = get_memory_store()
    total = store.count()
    # Re-run search with a high limit to compute buckets without adding a new
    # store method. Acceptable cost for a personal OS (memory count is small).
    all_mems = store.search(query="", limit=1000)
    by_category: dict[str, int] = {}
    by_importance = {"low": 0, "medium": 0, "high": 0}
    decayed_count = 0
    total_recall = 0
    for m in all_mems:
        cat = m.category.value if hasattr(m.category, "value") else str(m.category)
        by_category[cat] = by_category.get(cat, 0) + 1
        if m.importance < 0.34:
            by_importance["low"] += 1
        elif m.importance < 0.67:
            by_importance["medium"] += 1
        else:
            by_importance["high"] += 1
        if m.decayed:
            decayed_count += 1
        total_recall += m.recall_count
    return {
        "total": total,
        "by_category": by_category,
        "by_importance": by_importance,
        "decayed": decayed_count,
        "total_recalls": total_recall,
    }


@router.get("/{public_id}")
def get_memory(public_id: str) -> dict[str, Any]:
    """Fetch a single memory by public_id."""
    store = get_memory_store()
    mem = store.get(public_id)
    if mem is None:
        raise HTTPException(status_code=404, detail="memory not found")
    return _serialize(mem)


@router.patch("/{public_id}")
def update_memory(public_id: str, patch: MemoryUpdate) -> dict[str, Any]:
    """Update a memory's content, importance, and/or tags."""
    store = get_memory_store()
    if patch.content is not None and "\x00" in patch.content:
        raise HTTPException(status_code=400, detail="content contains null bytes")
    updated = store.update(
        public_id,
        content=patch.content,
        importance=patch.importance,
        tags=patch.tags,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="memory not found")
    return _serialize(updated)


@router.delete("/{public_id}")
def delete_memory(public_id: str) -> dict[str, Any]:
    """Delete a memory permanently."""
    store = get_memory_store()
    deleted = store.delete(public_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"status": "deleted", "public_id": public_id}
