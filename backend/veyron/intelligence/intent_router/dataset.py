"""Dataset generation for the intent router model.

Builds labeled examples from two sources:
  1. The 5000-record synthetic training data (primary bootstrap source)
  2. The expanded IntentDataset seed queries (augmentation)

Each example derives three labels:
  - mode:    "react" when simple, "plan" when planning_required or difficulty=hard
  - domain:  mapped from expected_tools (tool_name -> domain)
  - intent_category:  directly from the record's intent field

The pipeline is compatible with future real Veyron interaction data:
  UserInteraction records have detected_intent + selected_tools fields
  which map directly to the same label derivation logic.
"""

from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from veyron.intelligence.intent_router.schema import IntentRouterExample

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parents[3] / "data" / "training" / "synthetic_training_data.jsonl"

# Tool name -> domain mapping (covers all expected_tools in synthetic data).
_TOOL_TO_DOMAIN: dict[str, str] = {
    "filesystem_read": "filesystem",
    "filesystem_write": "filesystem",
    "terminal": "terminal",
    "system_monitor": "system",
    "project_analyzer": "project",
}
_DEFAULT_DOMAIN = "general"

# Multi-step patterns that increase plan mode probability.
_MULTI_STEP_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bfirst\b.*\bthen\b", re.IGNORECASE),
    re.compile(r"\bthen\b.*\bafter\b", re.IGNORECASE),
    re.compile(r"\bafter that\b", re.IGNORECASE),
    re.compile(r"\bstep by step\b", re.IGNORECASE),
    re.compile(r"\bcheck\b.*\band\b.*\bthen\b", re.IGNORECASE),
    re.compile(r"\bfirst\b.*\bafter\b", re.IGNORECASE),
    re.compile(r"\bbefore\b.*\bthen\b", re.IGNORECASE),
    re.compile(r"\bfinally\b", re.IGNORECASE),
    re.compile(r"\bmeanwhile\b", re.IGNORECASE),
    re.compile(r"\bsimultaneously\b", re.IGNORECASE),
    re.compile(r"\bin parallel\b", re.IGNORECASE),
    re.compile(r"\bfollow these steps\b", re.IGNORECASE),
    re.compile(r"\bsteps?\b.*\bthen\b", re.IGNORECASE),
    re.compile(r"\bmultistep\b", re.IGNORECASE),
    re.compile(r"\bmulti.step\b", re.IGNORECASE),
    re.compile(r"\bsequence\b.*\bof steps\b", re.IGNORECASE),
    re.compile(r"\bin order\b.*\bfirst\b", re.IGNORECASE),
    re.compile(r"\bproceed\b.*\bthen\b", re.IGNORECASE),
    re.compile(r"\bsubsequently\b", re.IGNORECASE),
    re.compile(r"\bone by one\b", re.IGNORECASE),
    re.compile(r"\bafter\b.*\bcheck\b", re.IGNORECASE),
    re.compile(r"\bthen\b.*\bcheck\b", re.IGNORECASE),
    re.compile(r"\bthen\b.*\brun\b", re.IGNORECASE),
    re.compile(r"\bthen\b.*\banalyze\b", re.IGNORECASE),
    re.compile(r"\bthen\b.*\breport\b", re.IGNORECASE),
    re.compile(r"\bif\b.*\bfail", re.IGNORECASE),
    re.compile(r"\bif\b.*\berror", re.IGNORECASE),
    re.compile(r"\btry\b.*\band\b.*\bif\b", re.IGNORECASE),
    re.compile(r"\b\d+\s+times?\b", re.IGNORECASE),
    re.compile(r"\btwice\b", re.IGNORECASE),
    re.compile(r"\bwith a delay\b", re.IGNORECASE),
    re.compile(r"\bthen later\b", re.IGNORECASE),
    re.compile(r"\bflag any\b", re.IGNORECASE),
    re.compile(r"\breport any\b", re.IGNORECASE),
    re.compile(r"\baudit\b", re.IGNORECASE),
    re.compile(r"\breview\b.*\band\b.*\bflag\b", re.IGNORECASE),
    re.compile(r"\bif\b.*\bstep\b.*\bfail", re.IGNORECASE),
    re.compile(r"\bcompare\b.*\bresult", re.IGNORECASE),
    re.compile(r"\brepeat\b", re.IGNORECASE),
    re.compile(r"\bevery\b.*\bseconds?\b", re.IGNORECASE),
    re.compile(r"\bcheck\b.*\band\b.*\bflag\b", re.IGNORECASE),
    re.compile(r"\binvestigate\b", re.IGNORECASE),
]

# Text-based domain keywords used as additional signal when tools list is empty.
_DOMAIN_TEXT_KEYWORDS: dict[str, list[str]] = {
    "system": ["cpu", "ram", "memory usage", "disk usage", "gpu", "temperature", "utilization", "memory", "process", "health", "swap", "uptime", "os version", "network", "port", "service", "system", "performance"],
    "filesystem": ["files", "folders", "directories", "permissions", "paths", "file", "folder", "directory", "path", "readme", "config", "listing", "tree", "contents", "size", "recursive"],
    "terminal": ["commands", "shell", "execute", "scripts", "command", "run", "build", "test", "deploy", "install", "npm", "git", "pip", "docker", "powershell", "cmd"],
    "project": ["project", "repo", "repository", "codebase", "architecture", "dependency", "tech stack", "framework", "coverage", "lint", "code quality", "refactor", "migrate"],
}


def derive_mode(planning_required: bool, difficulty: str, request: str = "") -> str:
    """Derive execution mode from planning requirement, difficulty, and text patterns."""
    if planning_required:
        return "plan"
    if difficulty == "hard":
        return "plan"
    if request:
        text_lower = request.lower()
        if any(p.search(text_lower) for p in _MULTI_STEP_PATTERNS):
            return "plan"
    return "react"


# Intent categories that operate on AI internals, not tool domains.
_NON_TOOL_INTENTS = {"memory_recall", "user_preference_update", "context_request"}


def derive_domain(expected_tools: list[str], request: str = "", intent: str = "") -> str:
    """Derive tool domain from expected tools, falling back to text keyword matching.
    
    Memory recall, user preference, and context request intents default to
    "general" since they deal with AI internals, not tool domains.
    """
    if intent in _NON_TOOL_INTENTS:
        return _DEFAULT_DOMAIN
    if expected_tools:
        for tool in expected_tools:
            domain = _TOOL_TO_DOMAIN.get(tool)
            if domain:
                return domain
    if request:
        text_lower = request.lower()
        scores: dict[str, int] = {}
        for domain, keywords in _DOMAIN_TEXT_KEYWORDS.items():
            scores[domain] = sum(1 for kw in keywords if kw in text_lower)
        if any(scores.values()):
            return max(scores, key=scores.get)
    return _DEFAULT_DOMAIN


def load_synthetic_records(path: str | Path = DATA_FILE) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        logger.warning("synthetic data file not found: %s", path)
        return []
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def record_to_example(record: dict[str, Any]) -> IntentRouterExample:
    """Convert a synthetic record to an IntentRouterExample with derived labels."""
    request = record.get("request", "")
    intent = record.get("intent", "conversation")
    tools = record.get("expected_tools", [])
    difficulty = record.get("difficulty", "easy")
    planning_required = record.get("planning_required", False)
    mode = derive_mode(planning_required, difficulty, request)
    domain = derive_domain(tools, request, intent)
    return IntentRouterExample(
        request=request,
        mode=mode,
        domain=domain,
        intent_category=intent,
        difficulty=difficulty,
    )


class IntentRouterDataset:
    """Container for intent router training examples."""

    def __init__(self, examples: list[IntentRouterExample] | None = None) -> None:
        self.examples: list[IntentRouterExample] = examples or []

    def add(self, example: IntentRouterExample) -> None:
        self.examples.append(example)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> IntentRouterExample:
        return self.examples[idx]

    @classmethod
    def from_synthetic(cls, path: str | Path = DATA_FILE) -> IntentRouterDataset:
        """Build dataset from the 5000-record synthetic training data."""
        records = load_synthetic_records(path)
        dataset = cls()
        for rec in records:
            dataset.add(record_to_example(rec))
        logger.info("built %d examples from synthetic data", len(dataset))
        return dataset

    def texts(self) -> list[str]:
        return [ex.request for ex in self.examples]

    def modes(self) -> list[str]:
        return [ex.mode for ex in self.examples]

    def domains(self) -> list[str]:
        return [ex.domain for ex in self.examples]

    def intents(self) -> list[str]:
        return [ex.intent_category for ex in self.examples]

    def label_counts(self) -> dict[str, dict[str, int]]:
        from collections import Counter
        return {
            "mode": dict(Counter(self.modes())),
            "domain": dict(Counter(self.domains())),
            "intent_category": dict(Counter(self.intents())),
        }

    def summary(self) -> dict[str, Any]:
        if not self.examples:
            return {"total": 0}
        counts = self.label_counts()
        return {
            "total": len(self.examples),
            "mode_distribution": counts["mode"],
            "domain_distribution": counts["domain"],
            "intent_distribution": counts["intent_category"],
        }

    def stratified_split(
        self, test_ratio: float = 0.2, seed: int = 42
    ) -> tuple[IntentRouterDataset, IntentRouterDataset]:
        """Split by intent_category (stratified) to preserve class balance."""
        rng = random.Random(seed)
        from collections import defaultdict
        by_intent: dict[str, list[IntentRouterExample]] = defaultdict(list)
        for ex in self.examples:
            by_intent[ex.intent_category].append(ex)

        train: list[IntentRouterExample] = []
        test: list[IntentRouterExample] = []
        for intent, items in by_intent.items():
            rng.shuffle(items)
            split = max(1, int(len(items) * (1 - test_ratio)))
            train.extend(items[:split])
            test.extend(items[split:])

        return IntentRouterDataset(train), IntentRouterDataset(test)

    @classmethod
    def from_jsonl(cls, path: str | Path) -> IntentRouterDataset:
        dataset = cls()
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                dataset.add(IntentRouterExample(
                    request=d["request"],
                    mode=d.get("mode", "react"),
                    domain=d.get("domain", "general"),
                    intent_category=d.get("intent_category", "conversation"),
                    difficulty=d.get("difficulty", "easy"),
                ))
        return dataset

    def to_jsonl(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for ex in self.examples:
                f.write(json.dumps({
                    "request": ex.request,
                    "mode": ex.mode,
                    "domain": ex.domain,
                    "intent_category": ex.intent_category,
                    "difficulty": ex.difficulty,
                }, ensure_ascii=False) + "\n")
        logger.info("saved %d examples to %s", len(self.examples), path)
