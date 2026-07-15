from __future__ import annotations

import hashlib
import json
import logging
import random
from collections import Counter
from pathlib import Path
from typing import Any

from veyron.intelligence.error_recovery.schema import (
    ErrorRecoveryExample,
    RecoveryAction,
)

logger = logging.getLogger(__name__)

random.seed(42)

SYNTHETIC_OUTPUT = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "training"
    / "synthetic_error_recovery_data.jsonl"
)

# ── Error pattern templates ────────────────────────────────────────────────────

_ERROR_KEYWORDS = {
    "timeout": ["timeout", "timed out", "took too long"],
    "invalid_input": ["invalid input", "validation error", "model_validate", "bad value"],
    "permission": ["permission", "denied", "not allowed", "unauthorized", "blocked"],
    "not_found": ["not found", "no such file", "does not exist", "cannot find"],
    "connection": ["connection", "refused", "unreachable", "network error", "reset"],
    "crash": ["exception", "traceback", "crashed", "segfault", "panic"],
    "oom": ["out of memory", "memory error", "no space", "disk full"],
    "syntax": ["syntax error", "parse error", "unexpected token", "invalid syntax"],
}

_TOOL_NAMES = [
    "filesystem_read",
    "filesystem_write",
    "terminal",
    "system_monitor",
    "project_analyzer",
]

_TASK_CONTEXTS = [
    "system management",
    "file operation",
    "tool execution",
    "project analysis",
    "debugging",
    "coding task",
    "planning task",
]

_PREVIOUS_ACTIONS = [
    "none",
    "retry",
    "modify_parameters",
    "alternative_tool",
    "fallback_llm",
]


def _classify_failure(error: str) -> str:
    err_lower = error.lower()
    for category, keywords in _ERROR_KEYWORDS.items():
        if any(kw in err_lower for kw in keywords):
            return category
    return "unknown"


def _sample_tool_error(tool: str, failure_category: str) -> str:
    errors_by_tool_failure: dict[str, dict[str, list[str]]] = {
        "filesystem_read": {
            "timeout": ["TIMEOUT after 10000ms reading file", "read timed out"],
            "invalid_input": ["invalid inputs: path must be a string", "validation error on path"],
            "permission": ["permission denied: access to path blocked", "not allowed to read this file"],
            "not_found": ["FileNotFoundError: no such file or directory", "path does not exist"],
            "connection": ["filesystem mount unreachable", "network drive disconnected"],
            "crash": ["segmentation fault during file read", "internal error reading file"],
            "oom": ["out of memory: file too large", "no space to buffer file contents"],
            "syntax": ["invalid path syntax: illegal characters", "parse error in path"],
            "unknown": ["unexpected error reading file", "operation failed"],
        },
        "filesystem_write": {
            "timeout": ["TIMEOUT after 15000ms writing file", "write timed out"],
            "invalid_input": ["invalid inputs: invalid file name", "validation error on content"],
            "permission": ["permission denied: cannot write to this location", "read only filesystem"],
            "not_found": ["FileNotFoundError: parent directory does not exist", "cannot create file in missing directory"],
            "connection": ["remote filesystem unavailable", "network write failed"],
            "crash": ["error during file write", "write operation crashed"],
            "oom": ["disk full: cannot write file", "no space left on device"],
            "syntax": ["invalid file name syntax", "illegal characters in path"],
            "unknown": ["unexpected error writing file", "write failed"],
        },
        "terminal": {
            "timeout": ["TIMEOUT after 30000ms: command did not complete", "process timed out"],
            "invalid_input": ["invalid inputs: command must be a string", "validation error on command"],
            "permission": ["permission denied: command not allowed", "access denied to execute"],
            "not_found": ["CommandNotFoundError: program not installed", "executable not found in PATH"],
            "connection": ["ConnectionError: could not reach remote host", "network unreachable"],
            "crash": ["ProcessExitedWithCode: exit code 1", "script crashed with traceback"],
            "oom": ["memory allocation failed during command", "out of memory: process killed"],
            "syntax": ["syntax error in command", "invalid shell syntax"],
            "unknown": ["command failed with unknown error", "unexpected process termination"],
        },
        "system_monitor": {
            "timeout": ["TIMEOUT after 5000ms collecting metrics", "sensor read timed out"],
            "invalid_input": ["invalid inputs: metric must be valid", "validation error on metric"],
            "permission": ["permission denied: cannot access performance counters", "elevation required"],
            "not_found": ["sensor not found on this system", "performance counter does not exist"],
            "connection": ["cannot connect to WMI service", "remote monitoring target unreachable"],
            "crash": ["internal monitoring error", "performance counter query failed"],
            "oom": ["out of memory collecting system data", "too many processes to enumerate"],
            "syntax": ["invalid metric name syntax", "bad query format"],
            "unknown": ["system monitoring failed", "unexpected sensor error"],
        },
        "project_analyzer": {
            "timeout": ["TIMEOUT after 60000ms analyzing project", "analysis timed out"],
            "invalid_input": ["invalid inputs: path must be a valid directory", "validation error"],
            "permission": ["permission denied: cannot read project files", "access denied to directory"],
            "not_found": ["project path does not exist", "no package files found"],
            "connection": ["cannot fetch remote dependencies", "package registry unreachable"],
            "crash": ["analyzer crashed: unexpected project structure", "internal analysis error"],
            "oom": ["out of memory analyzing project", "project too large to analyze"],
            "syntax": ["invalid project configuration syntax", "malformed package file"],
            "unknown": ["project analysis failed unexpectedly", "unable to analyze"],
        },
    }
    tool_errors = errors_by_tool_failure.get(tool, errors_by_tool_failure["terminal"])
    return random.choice(tool_errors.get(failure_category, tool_errors["unknown"]))


def _suggest_recovery(
    failure_category: str,
    tool: str,
    task_context: str,
    previous_action: str,
) -> RecoveryAction:
    if previous_action == "fallback_llm":
        return RecoveryAction.FALLBACK_LLM

    if failure_category == "permission":
        return RecoveryAction.CLARIFY

    if failure_category == "invalid_input":
        return RecoveryAction.CLARIFY

    if failure_category == "syntax":
        return RecoveryAction.CLARIFY

    if failure_category == "not_found":
        if tool in ("filesystem_read", "filesystem_write"):
            return RecoveryAction.MODIFY_PARAMETERS
        if tool == "terminal":
            return RecoveryAction.ALTERNATIVE_TOOL
        return RecoveryAction.MODIFY_PARAMETERS

    if failure_category == "connection":
        if previous_action == "retry":
            return RecoveryAction.ALTERNATIVE_TOOL
        return RecoveryAction.RETRY

    if failure_category == "timeout":
        if previous_action == "retry":
            return RecoveryAction.MODIFY_PARAMETERS
        if previous_action == "modify_parameters":
            return RecoveryAction.ALTERNATIVE_TOOL
        if tool in ("system_monitor", "filesystem_read"):
            return RecoveryAction.RETRY
        return RecoveryAction.RETRY

    if failure_category == "oom":
        if tool == "project_analyzer":
            return RecoveryAction.MODIFY_PARAMETERS
        return RecoveryAction.FALLBACK_LLM

    if failure_category == "crash":
        if previous_action == "retry":
            return RecoveryAction.MODIFY_PARAMETERS
        return RecoveryAction.RETRY

    if failure_category == "unknown":
        if previous_action == "none":
            return RecoveryAction.FALLBACK_LLM
        return RecoveryAction.FALLBACK_LLM

    return RecoveryAction.FALLBACK_LLM


def _generate_recovery_examples(target: int = 5000) -> list[ErrorRecoveryExample]:
    all_failure_categories = list(_ERROR_KEYWORDS.keys()) + ["unknown"]
    all_combos: list[tuple[str, str, str, str]] = []
    seen_set: set[str] = set()

    for tool in _TOOL_NAMES:
        for fc in all_failure_categories:
            msgs = _ERROR_KEYWORDS.get(fc, ["unknown error"])
            for msg in msgs:
                for ctx in _TASK_CONTEXTS:
                    for prev in _PREVIOUS_ACTIONS:
                        raw = f"{msg}|{tool}|{ctx}|{prev}"
                        h = hashlib.sha256(raw.encode()).hexdigest()[:16]
                        if h not in seen_set:
                            seen_set.add(h)
                            all_combos.append((msg, tool, ctx, prev, fc))

    random.shuffle(all_combos)

    if target > len(all_combos):
        num_extra = target - len(all_combos)
        for _ in range(num_extra):
            tool = random.choice(_TOOL_NAMES)
            fc = random.choice(all_failure_categories)
            msg = _sample_tool_error(tool, fc)
            ctx = random.choice(_TASK_CONTEXTS)
            prev = random.choice(_PREVIOUS_ACTIONS)
            raw = f"{msg}|{tool}|{ctx}|{prev}"
            h = hashlib.sha256(raw.encode()).hexdigest()[:16]
            if h not in seen_set:
                seen_set.add(h)
                all_combos.append((msg, tool, ctx, prev, fc))

    examples: list[ErrorRecoveryExample] = []
    for i, (msg, tool, ctx, prev, fc) in enumerate(all_combos[:target]):
        recovery_action = _suggest_recovery(fc, tool, ctx, prev)
        examples.append(ErrorRecoveryExample(
            error_message=msg,
            tool_name=tool,
            task_context=ctx,
            previous_action=prev,
            recovery_action=recovery_action,
            failure_category=fc,
        ))
        if (i + 1) % 1000 == 0:
            logger.info("generated %d recovery examples...", i + 1)

    return examples


class ErrorRecoveryDataset:
    def __init__(self, examples: list[ErrorRecoveryExample] | None = None) -> None:
        self.examples: list[ErrorRecoveryExample] = examples or []

    def add(self, example: ErrorRecoveryExample) -> None:
        self.examples.append(example)

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> ErrorRecoveryExample:
        return self.examples[idx]

    @classmethod
    def from_synthetic(cls, path: str | Path | None = None) -> ErrorRecoveryDataset:
        path = Path(path) if path else SYNTHETIC_OUTPUT
        if path.exists():
            return cls.from_jsonl(path)
        logger.info("generating synthetic error recovery data...")
        examples = _generate_recovery_examples()
        dataset = cls(examples)
        dataset.to_jsonl(path)
        return dataset

    @classmethod
    def from_jsonl(cls, path: str | Path) -> ErrorRecoveryDataset:
        dataset = cls()
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                dataset.add(ErrorRecoveryExample(
                    error_message=d["error_message"],
                    tool_name=d["tool_name"],
                    task_context=d.get("task_context", ""),
                    previous_action=d.get("previous_action", "none"),
                    recovery_action=RecoveryAction(d["recovery_action"]),
                    difficulty=d.get("difficulty", "moderate"),
                    failure_category=d.get("failure_category", "unknown"),
                ))
        return dataset

    def to_jsonl(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for ex in self.examples:
                f.write(json.dumps({
                    "error_message": ex.error_message,
                    "tool_name": ex.tool_name,
                    "task_context": ex.task_context,
                    "previous_action": ex.previous_action,
                    "recovery_action": ex.recovery_action.value,
                    "difficulty": ex.difficulty,
                    "failure_category": ex.failure_category,
                }, ensure_ascii=False) + "\n")

    def texts(self) -> list[str]:
        return [
            f"{ex.error_message} | tool: {ex.tool_name} | context: {ex.task_context} | previous: {ex.previous_action}"
            for ex in self.examples
        ]

    def labels(self) -> list[str]:
        return [ex.recovery_action.value for ex in self.examples]

    def label_counts(self) -> dict[str, int]:
        from collections import Counter
        return dict(Counter(self.labels()))

    def summary(self) -> dict[str, Any]:
        if not self.examples:
            return {"total": 0}
        return {
            "total": len(self.examples),
            "action_distribution": self.label_counts(),
            "tool_distribution": dict(
                Counter(ex.tool_name for ex in self.examples)
            ),
        }

    def stratified_split(
        self, test_ratio: float = 0.2, seed: int = 42
    ) -> tuple[ErrorRecoveryDataset, ErrorRecoveryDataset]:
        rng = random.Random(seed)
        from collections import defaultdict
        by_action: dict[str, list[ErrorRecoveryExample]] = defaultdict(list)
        for ex in self.examples:
            by_action[ex.recovery_action.value].append(ex)

        train: list[ErrorRecoveryExample] = []
        test: list[ErrorRecoveryExample] = []
        for action, items in by_action.items():
            rng.shuffle(items)
            split = max(1, int(len(items) * (1 - test_ratio)))
            train.extend(items[:split])
            test.extend(items[split:])

        return ErrorRecoveryDataset(train), ErrorRecoveryDataset(test)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger.info("Generating synthetic error recovery dataset...")
    examples = _generate_recovery_examples()
    dataset = ErrorRecoveryDataset(examples)
    dataset.to_jsonl(SYNTHETIC_OUTPUT)
    counts = dataset.label_counts()
    print(f"Generated {len(dataset)} examples")
    print("Action distribution:")
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {k:25s} {v:4d} ({v/len(dataset)*100:5.1f}%)")


if __name__ == "__main__":
    main()
