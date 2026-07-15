from __future__ import annotations

import hashlib
import json
import logging
import random
from collections import Counter
from pathlib import Path
from typing import Any

from veyron.intelligence.planning.schema import (
    PLANNING_STEP_CATEGORIES,
    PlanningExample,
    step_count_to_bin,
)

logger = logging.getLogger(__name__)

random.seed(42)

SYNTHETIC_OUTPUT = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "training"
    / "synthetic_planning_data.jsonl"
)

PLANNING_CATEGORIES = [
    "research",
    "file_operation",
    "tool_execution",
    "coding_task",
    "debugging",
    "system_management",
    "project_analysis",
    "question_answering",
]

SIMPLES = [
    "what time is it",
    "tell me a joke",
    "how are you",
    "what is 2 + 2",
    "list files in current directory",
    "check cpu usage",
    "show disk space",
    "who created python",
    "what is the weather",
    "translate hello to spanish",
    "remind me to buy milk",
    "search for pandas documentation",
    "open my project folder",
    "check my python version",
    "what is the capital of france",
    "send a message to john",
]

SIMPLES_PLAN = [False] * len(SIMPLES)
SIMPLES_STEPS = [0] * len(SIMPLES)
SIMPLES_CATS: list[list[str]] = [[] for _ in SIMPLES]

COMPLEX_MULTI = [
    "analyze this python project and generate documentation",
    "refactor the codebase to use async patterns throughout",
    "find performance bottlenecks and optimize the application",
    "migrate from sqlite to postgresql with full data migration",
    "build a rest api for the existing database models",
    "create a complete monitoring dashboard for the system",
    "set up ci/cd pipeline with github actions and docker",
    "implement unit tests for all modules in the project",
    "review the codebase for security vulnerabilities",
    "profile the application and identify memory leaks",
    "convert the monolithic app to microservices",
    "analyze test coverage and write missing tests",
]

COMPLEX_MULTI_PLAN = [True] * len(COMPLEX_MULTI)
COMPLEX_MULTI_STEPS = [random.randint(4, 8) for _ in COMPLEX_MULTI]
COMPLEX_MULTI_CATS = [
    ["research", "project_analysis", "tool_execution", "coding_task"],
    ["research", "project_analysis", "coding_task", "debugging"],
    ["research", "tool_execution", "project_analysis", "debugging"],
    ["research", "file_operation", "tool_execution", "coding_task"],
    ["research", "coding_task", "tool_execution", "question_answering"],
    ["research", "coding_task", "system_management", "project_analysis"],
    ["research", "file_operation", "tool_execution", "system_management"],
    ["research", "coding_task", "debugging", "file_operation"],
    ["research", "project_analysis", "debugging", "question_answering"],
    ["research", "tool_execution", "project_analysis", "coding_task"],
    ["research", "coding_task", "project_analysis", "tool_execution"],
    ["research", "file_operation", "coding_task", "debugging"],
]

COMPLEX_BUILD = [
    "write a python script to process csv files and generate reports",
    "create a web scraper that extracts product data from ecommerce sites",
    "build a chatbot using the openai api for customer support",
    "develop a rest client library with retry logic and caching",
    "implement a data pipeline that ingests logs and stores them in elasticsearch",
    "create a command line tool for managing docker containers",
    "write a background job processor with worker pools and retries",
    "implement a rate limiter middleware for fastapi applications",
    "build a file watcher that triggers actions on file changes",
    "create an api rate limit analyzer with real-time metrics",
]

COMPLEX_BUILD_PLAN = [True] * len(COMPLEX_BUILD)
COMPLEX_BUILD_STEPS = [random.randint(3, 6) for _ in COMPLEX_BUILD]
COMPLEX_BUILD_CATS = [
    ["research", "coding_task", "file_operation", "debugging"],
    ["research", "tool_execution", "coding_task", "debugging"],
    ["research", "coding_task", "tool_execution", "question_answering"],
    ["research", "coding_task", "tool_execution", "debugging"],
    ["research", "file_operation", "tool_execution", "coding_task"],
    ["research", "coding_task", "tool_execution", "system_management"],
    ["research", "coding_task", "debugging", "tool_execution"],
    ["research", "coding_task", "debugging", "tool_execution"],
    ["research", "coding_task", "file_operation", "tool_execution"],
    ["research", "tool_execution", "coding_task", "project_analysis"],
]

COMPLEX_DEBUG = [
    "my application crashes when processing large files, find the bug",
    "the api returns 500 errors intermittently, debug the issue",
    "memory usage grows continuously, identify the leak",
    "database queries are too slow, optimize the slow queries",
    "authentication is failing for some users, investigate",
    "the build pipeline is failing with cryptic errors",
    "cors errors in the browser, fix the api configuration",
]

COMPLEX_DEBUG_PLAN = [True] * len(COMPLEX_DEBUG)
COMPLEX_DEBUG_STEPS = [random.randint(3, 6) for _ in COMPLEX_DEBUG]
COMPLEX_DEBUG_CATS = [
    ["research", "debugging", "tool_execution", "coding_task"],
    ["research", "debugging", "tool_execution", "file_operation"],
    ["research", "debugging", "tool_execution", "coding_task"],
    ["research", "debugging", "tool_execution", "system_management"],
    ["research", "debugging", "coding_task", "file_operation"],
    ["research", "debugging", "tool_execution", "file_operation"],
    ["research", "debugging", "coding_task", "tool_execution"],
]

COMPLEX_RESEARCH = [
    "research modern python async patterns and write a guide",
    "compare the top 5 python web frameworks for our use case",
    "investigate best practices for microservice communication",
    "study the performance characteristics of different databases",
    "analyze the tradeoffs between monolith and microservices",
]

COMPLEX_RESEARCH_PLAN = [True] * len(COMPLEX_RESEARCH)
COMPLEX_RESEARCH_STEPS = [random.randint(3, 5) for _ in COMPLEX_RESEARCH]
COMPLEX_RESEARCH_CATS = [
    ["research", "question_answering", "file_operation", "project_analysis"],
    ["research", "project_analysis", "question_answering", "file_operation"],
    ["research", "question_answering", "project_analysis", "tool_execution"],
    ["research", "file_operation", "question_answering", "project_analysis"],
    ["research", "project_analysis", "question_answering", "file_operation"],
]

COMPLEX_SIMPLE_TOOL = [
    "search for files containing the word deprecated",
    "find all python files that import os module",
    "count lines of code in the project by language",
    "show me the git log for the last 3 months",
    "find all functions without type hints in the codebase",
    "calculate the total size of all log files",
    "list all running processes sorted by memory usage",
]

COMPLEX_SIMPLE_TOOL_PLAN = [False] * len(COMPLEX_SIMPLE_TOOL)
COMPLEX_SIMPLE_TOOL_STEPS = [random.randint(0, 1) for _ in COMPLEX_SIMPLE_TOOL]
COMPLEX_SIMPLE_TOOL_CATS = [
    ["file_operation", "tool_execution"],
    ["file_operation", "tool_execution"],
    ["file_operation", "tool_execution"],
    ["tool_execution", "file_operation"],
    ["file_operation", "coding_task"],
    ["file_operation", "tool_execution"],
    ["tool_execution", "system_management"],
]


def _feature_text(
    request: str,
    intent_category: str = "general",
    complexity: str = "simple",
) -> str:
    return f"{request} | intent: {intent_category} | complexity: {complexity}"


def _intent_for(request: str) -> str:
    req_lower = request.lower()
    if any(kw in req_lower for kw in ["write", "build", "create", "implement", "develop", "convert", "refactor", "migrate"]):
        return "coding_task"
    if any(kw in req_lower for kw in ["debug", "fix", "issue", "bug", "crash", "error", "failure"]):
        return "debugging"
    if any(kw in req_lower for kw in ["research", "investigate", "compare", "study", "analyze", "guide", "best practice"]):
        return "research"
    if any(kw in req_lower for kw in ["analyze", "profile", "review", "audit", "coverage"]):
        return "project_analysis"
    if any(kw in req_lower for kw in ["set up", "configure", "install", "deploy"]):
        return "system_management"
    if any(kw in req_lower for kw in ["search", "find", "count", "calculate", "list", "show"]):
        return "file_operation"
    return "conversation"


def _complexity_for(request: str) -> str:
    req_lower = request.lower()
    if any(kw in req_lower for kw in ["analyze test coverage", "migrate from", "convert monolithic", "build a rest api"]):
        return "complex"
    if any(kw in req_lower for kw in ["analyze", "refactor", "migrate", "build", "create", "develop", "implement", "research"]):
        return "moderate"
    return "simple"


def _categories_to_binary(categories: list[str]) -> list[int]:
    return [1 if cat in categories else 0 for cat in PLANNING_STEP_CATEGORIES]


def _generate_examples(target: int = 3000) -> list[PlanningExample]:
    all_simple: list[tuple[str, bool, int, list[str]]] = []
    all_simple.extend(zip(SIMPLES, SIMPLES_PLAN, SIMPLES_STEPS, SIMPLES_CATS))
    all_complex_multi: list[tuple[str, bool, int, list[str]]] = list(
        zip(COMPLEX_MULTI, COMPLEX_MULTI_PLAN, COMPLEX_MULTI_STEPS, COMPLEX_MULTI_CATS)
    )
    all_complex_build: list[tuple[str, bool, int, list[str]]] = list(
        zip(COMPLEX_BUILD, COMPLEX_BUILD_PLAN, COMPLEX_BUILD_STEPS, COMPLEX_BUILD_CATS)
    )
    all_complex_debug: list[tuple[str, bool, int, list[str]]] = list(
        zip(COMPLEX_DEBUG, COMPLEX_DEBUG_PLAN, COMPLEX_DEBUG_STEPS, COMPLEX_DEBUG_CATS)
    )
    all_complex_research: list[tuple[str, bool, int, list[str]]] = list(
        zip(COMPLEX_RESEARCH, COMPLEX_RESEARCH_PLAN, COMPLEX_RESEARCH_STEPS, COMPLEX_RESEARCH_CATS)
    )
    all_simple_tool: list[tuple[str, bool, int, list[str]]] = list(
        zip(COMPLEX_SIMPLE_TOOL, COMPLEX_SIMPLE_TOOL_PLAN, COMPLEX_SIMPLE_TOOL_STEPS, COMPLEX_SIMPLE_TOOL_CATS)
    )

    groups = [
        ("simple", all_simple),
        ("complex_multi", all_complex_multi),
        ("complex_build", all_complex_build),
        ("complex_debug", all_complex_debug),
        ("complex_research", all_complex_research),
        ("simple_tool", all_simple_tool),
    ]

    examples: list[PlanningExample] = []
    seen: set[str] = set()

    for _ in range(target):
        group_name, group = random.choice(groups)
        req, _, steps, cats = random.choice(group)
        raw = f"{req}|{group_name}"
        h = hashlib.sha256(raw.encode()).hexdigest()[:16]

        if h not in seen:
            seen.add(h)
            intent_cat = _intent_for(req)
            complexity = _complexity_for(req)
            requires_plan = _should_plan(req, group_name)

            examples.append(PlanningExample(
                request=req,
                intent_category=intent_cat,
                complexity=complexity,
                requires_plan=requires_plan,
                estimated_steps=max(1, steps) if requires_plan else 0,
                step_categories=cats if requires_plan else [],
            ))

    return examples[:target]


def _should_plan(request: str, group: str) -> bool:
    if group in ("complex_multi", "complex_build", "complex_debug", "complex_research"):
        return True
    return False


def stratified_split(
    examples: list[PlanningExample], test_ratio: float = 0.2, seed: int = 42
) -> tuple[list[PlanningExample], list[PlanningExample]]:
    rng = random.Random(seed)
    by_plan: dict[str, list[PlanningExample]] = {"plan": [], "no_plan": []}
    for ex in examples:
        key = "plan" if ex.requires_plan else "no_plan"
        by_plan[key].append(ex)

    train: list[PlanningExample] = []
    test: list[PlanningExample] = []
    for items in by_plan.values():
        rng.shuffle(items)
        split = max(1, int(len(items) * (1 - test_ratio)))
        train.extend(items[:split])
        test.extend(items[split:])

    return train, test


class PlanningDataset:
    def __init__(self, examples: list[PlanningExample] | None = None) -> None:
        self.examples: list[PlanningExample] = examples or []

    def add(self, example: PlanningExample) -> None:
        self.examples.append(example)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> PlanningExample:
        return self.examples[idx]

    @classmethod
    def from_synthetic(cls, path: str | Path | None = None) -> PlanningDataset:
        path = Path(path) if path else SYNTHETIC_OUTPUT
        if path.exists():
            return cls.from_jsonl(path)
        logger.info("generating synthetic planning data...")
        examples = _generate_examples()
        dataset = cls(examples)
        dataset.to_jsonl(path)
        return dataset

    @classmethod
    def from_jsonl(cls, path: str | Path) -> PlanningDataset:
        dataset = cls()
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                dataset.add(PlanningExample(
                    request=d["request"],
                    intent_category=d.get("intent_category", "general"),
                    complexity=d.get("complexity", "simple"),
                    requires_plan=d.get("requires_plan", False),
                    estimated_steps=d.get("estimated_steps", 0),
                    step_categories=d.get("step_categories", []),
                    available_tools=d.get("available_tools", []),
                    failure_category=d.get("failure_category", "unknown"),
                ))
        return dataset

    def to_jsonl(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for ex in self.examples:
                f.write(json.dumps({
                    "request": ex.request,
                    "intent_category": ex.intent_category,
                    "complexity": ex.complexity,
                    "requires_plan": ex.requires_plan,
                    "estimated_steps": ex.estimated_steps,
                    "step_categories": ex.step_categories,
                    "available_tools": ex.available_tools,
                    "failure_category": ex.failure_category,
                }, ensure_ascii=False) + "\n")

    def texts(self) -> list[str]:
        return [
            f"{ex.request} | intent: {ex.intent_category} | complexity: {ex.complexity}"
            for ex in self.examples
        ]

    def plan_labels(self) -> list[bool]:
        return [ex.requires_plan for ex in self.examples]

    def steps_labels(self) -> list[str]:
        return [step_count_to_bin(ex.estimated_steps) for ex in self.examples]

    def categories_matrix(self) -> list[list[int]]:
        return [_categories_to_binary(ex.step_categories) for ex in self.examples]

    def label_counts(self) -> dict[str, int]:
        return dict(Counter(self.plan_labels()))

    def summary(self) -> dict[str, Any]:
        if not self.examples:
            return {"total": 0}
        plan_count = sum(1 for ex in self.examples if ex.requires_plan)
        return {
            "total": len(self.examples),
            "requires_plan": plan_count,
            "no_plan": len(self.examples) - plan_count,
            "action_distribution": self.label_counts(),
        }

    def stratified_split(
        self, test_ratio: float = 0.2, seed: int = 42
    ) -> tuple[PlanningDataset, PlanningDataset]:
        train_ex, test_ex = stratified_split(self.examples, test_ratio, seed)
        return PlanningDataset(train_ex), PlanningDataset(test_ex)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger.info("Generating synthetic planning dataset...")
    examples = _generate_examples()
    dataset = PlanningDataset(examples)
    dataset.to_jsonl(SYNTHETIC_OUTPUT)
    plan_count = sum(1 for ex in examples if ex.requires_plan)
    print(f"Generated {len(examples)} examples ({plan_count} require planning, {len(examples) - plan_count} do not)")


if __name__ == "__main__":
    main()
