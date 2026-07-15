"""Memory layer — persistent long-term memory.

MemoryStore provides CRUD, text search, and context injection.
Phase 5 will add vector embeddings (Chroma).
"""

from veyron.memory.store import MemoryStore, get_memory_store, reset_memory_store

__all__ = [
    "MemoryStore",
    "get_memory_store",
    "reset_memory_store",
]
