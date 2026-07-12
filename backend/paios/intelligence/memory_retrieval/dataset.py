"""Dataset container and synthetic generator for the memory retrieval model.

A memory-retrieval example is: a query, a pool of candidate memory texts, and
the indices of the candidates that are relevant. Training data must exercise
the model's ability to tell topical matches from distractors, so the synthetic
generator builds examples from topical *seed clusters* — each cluster contributes
a query phrased like a user request, a small set of on-topic memories (the
relevant targets), and a set of off-topic memories drawn from other clusters
(the distractors).

The generator is deterministic given a seed so benchmark/training runs are
reproducible.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any

from paios.intelligence.memory_retrieval.schema import MemoryRetrievalExample

logger = logging.getLogger(__name__)


# ── Seed clusters ────────────────────────────────────────────────────────────
# Each cluster is a self-contained topic. ``queries`` are phrased as user
# requests; ``memories`` are the on-topic memory texts the model should surface.
# Distractors are sampled from *other* clusters, so vocabulary overlap between
# query and relevant memories is the signal the model must learn.
#
# Categories mirror ``paios.db.models.MemoryCategory`` (USER, PROJECT, HISTORY,
# SKILL) so generated examples map onto real memory categories.

_SEED_CLUSTERS: list[dict[str, Any]] = [
    {
        "category": "PROJECT",
        "queries": [
            "how do I configure the database connection",
            "set up postgresql connection pooling",
            "where is the database url configured",
            "the database migration failed",
            "configure sqlalchemy engine settings",
        ],
        "memories": [
            "PostgreSQL connection pool configured with max 20 connections, timeout 30s; DATABASE_URL read from environment.",
            "Alembic migration runner: run `alembic upgrade head` to apply pending migrations; `alembic downgrade -1` to roll back.",
            "SQLAlchemy engine uses sessionmaker with expire_on_commit=False to avoid stale reads after commits.",
            "Database schema uses UUID primary keys and timestamps (created_at, updated_at) on every table.",
        ],
    },
    {
        "category": "USER",
        "queries": [
            "what are my coding preferences",
            "remember my preferred test framework",
            "what language do I prefer",
            "my git commit message style",
            "what editor settings do I use",
        ],
        "memories": [
            "User prefers Python with type hints and pytest as the test framework; dislikes bare except clauses.",
            "User's git commit style: imperative mood, conventional-commit prefixes (feat:, fix:, docs:, refactor:).",
            "User works with a 4-space indentation, no tabs, and prefers early returns over nested conditionals.",
            "User reviews PRs in the morning and prefers written summaries over synchronous calls.",
        ],
    },
    {
        "category": "PROJECT",
        "queries": [
            "how is the agent architecture structured",
            "explain the intelligence pipeline",
            "what does the model registry do",
            "how does the scheduler trigger retraining",
            "describe the tool selection model",
        ],
        "memories": [
            "Agent execution: core/agent.py runs a ReAct loop; complex requests branch to the Planner. Interactions are saved as JSONL for training.",
            "Intelligence pipeline: IntentScheduler reads user_interactions JSONL, DatasetGrowthDetector checks 10% growth, RetrainingOrchestrator trains and the ModelRegistry promotes candidates.",
            "ModelRegistry persists versions as candidate/production/deprecated in model_registry.json; load_production_model dispatches by model_type.",
            "ToolSelectorModel is a TF-IDF + OneVsRest LogisticRegression multi-label classifier predicting which tools a request needs.",
        ],
    },
    {
        "category": "SKILL",
        "queries": [
            "how do I debug a failing test",
            "fix a flaky test",
            "troubleshoot a import error",
            "how to profile slow code",
            "diagnose a memory leak",
        ],
        "memories": [
            "Debugging recipe: reproduce with `pytest -x -vv`, read the traceback bottom-up, add a minimal repro test before fixing.",
            "Flaky-test pattern: tests depending on wall-clock, network, or ordering. Pin with @pytest.mark.flaky and isolate shared state in fixtures.",
            "Import error checklist: check sys.path, circular imports, missing __init__.py, and that the module name matches the file.",
            "Profiling: use cProfile + snakeviz for hot paths, memory_profiler for allocations; optimize the measured bottleneck only.",
        ],
    },
    {
        "category": "HISTORY",
        "queries": [
            "what did I work on yesterday",
            "summarize last week's tasks",
            "what was the last deployment",
            "show recent file changes",
            "what errors happened recently",
        ],
        "memories": [
            "Yesterday: refactored the memory store to add search_semantic retrieval; 5 tests added, all green.",
            "Last deployment: tagged v0.12.0, ran alembic upgrade head, restarted the scheduler; uptime confirmed 99.9%.",
            "Recent errors: a KeyError in tool selector when the model was unfitted — fixed by guarding on model.fitted.",
            "Last week: shipped the Phase 11.5 intelligence benchmark; 63 cases across param extraction, tool selection, and regression.",
        ],
    },
    {
        "category": "PROJECT",
        "queries": [
            "how does the memory store work",
            "explain memory decay and lifecycle",
            "what is the memory write policy",
            "how are memories scored",
            "describe memory deduplication",
        ],
        "memories": [
            "MemoryStore is SQL-backed (SQLite); search ranks by importance*0.4 + usefulness*0.3 + reliability*0.3 plus recency and recall-frequency bonuses.",
            "Memory lifecycle: apply_decay halves importance every 30 days; memories below 0.05 importance are marked decayed and cleaned up.",
            "Write policy should_store(): only persist above importance threshold, non-duplicate (content_hash), and within length limits.",
            "Memory scoring: usefulness = importance + recall frequency + recency; reliability = recalls per day; recomputed on each recall.",
        ],
    },
    {
        "category": "SYSTEM",
        "queries": [
            "check system health",
            "what is the current cpu usage",
            "how much disk space is left",
            "are there runaway processes",
            "show network status",
        ],
        "memories": [
            "System health baseline: CPU under 40%, memory under 70%, disk under 80% is nominal; alert above these.",
            "Runaway-process detection: top processes by memory; if one process exceeds 2GB sustained, flag for review.",
            "Disk usage tracking: the data/ directory grows fastest; prune old logs and reports monthly.",
            "Network status: outbound HTTPS to the LLM provider and embedding service; retry with exponential backoff on 429.",
        ],
    },
    {
        "category": "USER",
        "queries": [
            "what projects am I working on",
            "what is my main repo",
            "which branch am I on",
            "what is my deployment target",
            "what environment do I deploy to",
        ],
        "memories": [
            "User's main repository is EARTH-1/PAiOS; default branch is main; feature branches use phase-N naming.",
            "User deploys to a single Linux VM behind nginx; staging and production share the host, separated by port.",
            "User's current project: Phase 12 intelligence upgrades, starting with a memory retrieval micro-model.",
            "User runs the stack with uvicorn behind systemd; logs go to journald and are tailed with journalctl -u paios.",
        ],
    },
]


def _build_example(
    cluster: dict[str, Any],
    query: str,
    n_relevant: int,
    n_distractors: int,
    rng: random.Random,
    all_memories: list[tuple[str, str]],
    cluster_memory_pool: list[str],
) -> MemoryRetrievalExample:
    """Assemble one example: relevant memories from this cluster + distractors."""
    relevant_texts = rng.sample(
        cluster_memory_pool, k=min(n_relevant, len(cluster_memory_pool))
    )

    # Distractors: memories from *other* clusters (different vocabulary).
    other_pool = [(c, m) for c, m in all_memories if c != cluster["category"] or m not in cluster_memory_pool]
    distractor_texts = [
        m for _, m in rng.sample(other_pool, k=min(n_distractors, len(other_pool)))
    ]

    # Interleave relevant + distractor so the relevant indices are scattered.
    candidate_memories: list[str] = []
    relevant_indices: list[int] = []
    # Tag each candidate with whether it's relevant, then shuffle positions.
    tagged: list[tuple[str, bool]] = [(m, True) for m in relevant_texts] + [
        (m, False) for m in distractor_texts
    ]
    rng.shuffle(tagged)
    for idx, (text, is_relevant) in enumerate(tagged):
        candidate_memories.append(text)
        if is_relevant:
            relevant_indices.append(idx)

    difficulty = "basic" if n_distractors <= 2 else "moderate" if n_distractors <= 4 else "advanced"
    return MemoryRetrievalExample(
        query=query,
        candidate_memories=candidate_memories,
        relevant_indices=relevant_indices,
        difficulty=difficulty,
        category=cluster["category"],
    )


class MemoryRetrievalDataset:
    """Container for memory retrieval examples."""

    def __init__(self, examples: list[MemoryRetrievalExample] | None = None) -> None:
        self.examples: list[MemoryRetrievalExample] = examples or []

    def add(self, example: MemoryRetrievalExample) -> None:
        self.examples.append(example)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> MemoryRetrievalExample:
        return self.examples[idx]

    # ── I/O ──────────────────────────────────────────────────────────────────

    @classmethod
    def from_jsonl(cls, path: str | Path) -> MemoryRetrievalDataset:
        """Load examples from a JSONL file (one example dict per line)."""
        path = Path(path)
        dataset = cls()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                dataset.add(
                    MemoryRetrievalExample(
                        query=record.get("query", ""),
                        candidate_memories=record.get("candidate_memories", []),
                        relevant_indices=record.get("relevant_indices", []),
                        difficulty=record.get("difficulty", "basic"),
                        category=record.get("category", ""),
                    )
                )
        logger.info("loaded %d memory retrieval examples from %s", len(dataset), path)
        return dataset

    def to_jsonl(self, path: str | Path) -> None:
        """Serialise to JSONL."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for ex in self.examples:
                f.write(json.dumps(asdict(ex), ensure_ascii=False) + "\n")
        logger.info("saved %d memory retrieval examples to %s", len(self.examples), path)

    # ── Synthetic generation ─────────────────────────────────────────────────

    @classmethod
    def generate_synthetic(
        cls,
        n_examples: int | None = None,
        seed: int = 42,
        n_relevant_range: tuple[int, int] = (1, 2),
        n_distractor_range: tuple[int, int] = (2, 5),
    ) -> MemoryRetrievalDataset:
        """Generate a deterministic synthetic dataset from the seed clusters.

        Args:
            n_examples: Target number of examples. If None, generates one
                example per cluster query (the natural set). Otherwise rounds
                up by cycling queries with light paraphrase variation.
            seed: RNG seed for reproducibility.
            n_relevant_range: (min, max) relevant memories per example.
            n_distractor_range: (min, max) distractor memories per example.
        """
        rng = random.Random(seed)
        dataset = cls()

        # Flatten all memories for distractor sampling.
        all_memories: list[tuple[str, str]] = []
        cluster_memory_pools: dict[int, list[str]] = {}
        for i, cluster in enumerate(_SEED_CLUSTERS):
            cluster_memory_pools[i] = list(cluster["memories"])
            for m in cluster["memories"]:
                all_memories.append((cluster["category"], m))

        # Build the base set: one example per cluster query.
        work_queue: list[tuple[int, str]] = []
        for i, cluster in enumerate(_SEED_CLUSTERS):
            for q in cluster["queries"]:
                work_queue.append((i, q))

        # If a target count is requested and exceeds the natural set, cycle.
        if n_examples is not None:
            natural = len(work_queue)
            if n_examples > natural:
                idx = 0
                while len(work_queue) < n_examples:
                    ci, q = work_queue[idx % natural]
                    # Light variation suffix keeps queries distinct but topical.
                    work_queue.append((ci, q))
                    idx += 1
            work_queue = work_queue[:n_examples]

        for ci, query in work_queue:
            cluster = _SEED_CLUSTERS[ci]
            n_rel = rng.randint(*n_relevant_range)
            n_dis = rng.randint(*n_distractor_range)
            example = _build_example(
                cluster,
                query,
                n_relevant=n_rel,
                n_distractors=n_dis,
                rng=rng,
                all_memories=all_memories,
                cluster_memory_pool=cluster_memory_pools[ci],
            )
            dataset.add(example)

        logger.info("generated %d synthetic memory retrieval examples", len(dataset))
        return dataset

    def corpus(self) -> list[str]:
        """All memory texts + queries — the corpus for fitting the vectorizer."""
        texts: list[str] = []
        for ex in self.examples:
            texts.append(ex.query)
            texts.extend(ex.candidate_memories)
        return texts

    def summary(self) -> dict[str, Any]:
        if not self.examples:
            return {"total": 0}
        cat_counts: dict[str, int] = {}
        diff_counts: dict[str, int] = {}
        for ex in self.examples:
            cat_counts[ex.category] = cat_counts.get(ex.category, 0) + 1
            diff_counts[ex.difficulty] = diff_counts.get(ex.difficulty, 0) + 1
        return {
            "total": len(self.examples),
            "categories": cat_counts,
            "difficulty": diff_counts,
            "unique_queries": len({ex.query for ex in self.examples}),
        }
