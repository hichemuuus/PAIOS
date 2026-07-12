"""Dataset validator — checks quality and correctness of training examples.

Validates:
  - Intent categories against the known taxonomy
  - Tool names against the live tool registry
  - Duplicate entries (by content hash)
  - Missing or empty required fields
  - Produces a structured quality report
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from paios.intelligence.training.dataset import TrainingDataset, TrainingExample
from paios.intelligence.training.preparation.splitter import INTENT_CATEGORIES
from paios.tools.registry import get_registry

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"request", "intent"}
REQUIRED_FIELDS_SYNTHETIC = {"request", "intent", "expected_tools", "difficulty", "planning_required"}


class ValidationReport:
    def __init__(self) -> None:
        self.total: int = 0
        self.valid: int = 0
        self.invalid: int = 0
        self.missing_fields: list[dict[str, Any]] = []
        self.invalid_intents: list[dict[str, Any]] = []
        self.invalid_tools: list[dict[str, Any]] = []
        self.duplicates: list[dict[str, Any]] = []
        self.intent_distribution: dict[str, int] = {}
        self.tool_distribution: dict[str, int] = {}
        self.difficulty_distribution: dict[str, int] = {}

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 1.0
        return round(self.valid / self.total, 4)

    def merge(self, other: ValidationReport) -> None:
        self.total += other.total
        self.valid += other.valid
        self.invalid += other.invalid
        self.missing_fields.extend(other.missing_fields)
        self.invalid_intents.extend(other.invalid_intents)
        self.invalid_tools.extend(other.invalid_tools)
        self.duplicates.extend(other.duplicates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "valid": self.valid,
            "invalid": self.invalid,
            "pass_rate": self.pass_rate,
            "issues": {
                "missing_fields": len(self.missing_fields),
                "invalid_intents": len(self.invalid_intents),
                "invalid_tools": len(self.invalid_tools),
                "duplicates": len(self.duplicates),
            },
            "intent_distribution": dict(
                sorted(self.intent_distribution.items(), key=lambda x: -x[1])
            ),
            "tool_distribution": dict(
                sorted(self.tool_distribution.items(), key=lambda x: -x[1])
            ),
            "difficulty_distribution": dict(
                sorted(self.difficulty_distribution.items(), key=lambda x: -x[1])
            ),
        }


class DatasetValidator:
    def __init__(self, known_tools: list[str] | None = None) -> None:
        self.known_tools = known_tools
        self._registry_loaded = False

    def _get_known_tools(self) -> list[str]:
        if self.known_tools is not None:
            return self.known_tools
        if not self._registry_loaded:
            try:
                self.known_tools = get_registry().names()
            except Exception:
                self.known_tools = []
            self._registry_loaded = True
        return self.known_tools or []

    def validate_jsonl(self, path: str | Path) -> ValidationReport:
        report = ValidationReport()
        seen_hashes: set[str] = set()
        intent_counter: Counter = Counter()
        tool_counter: Counter = Counter()
        difficulty_counter: Counter = Counter()
        known_tools = self._get_known_tools()

        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                report.total += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    report.invalid += 1
                    report.missing_fields.append({"line": line_no, "error": f"invalid JSON: {e}"})
                    continue

                errors: list[str] = []

                missing = self._check_missing_fields(record)
                if missing:
                    errors.append(f"missing fields: {missing}")
                    report.missing_fields.append({"line": line_no, "record": record, "missing": missing})

                intent_ok = self._check_intent(record, line_no, report)
                if not intent_ok:
                    errors.append("invalid intent")

                tools_ok = self._check_tools(record, line_no, report, known_tools)
                if not tools_ok:
                    errors.append("invalid tools")

                dup = self._check_duplicate(record, seen_hashes, line_no, report)

                if errors:
                    report.invalid += 1
                else:
                    report.valid += 1

                intent = record.get("intent", "unknown")
                intent_counter[intent] += 1
                for tool in record.get("expected_tools", []):
                    tool_counter[tool] += 1
                diff = record.get("difficulty", "unknown")
                difficulty_counter[diff] += 1

        report.intent_distribution = dict(intent_counter)
        report.tool_distribution = dict(tool_counter)
        report.difficulty_distribution = dict(difficulty_counter)
        return report

    def validate_dataset(self, dataset: TrainingDataset) -> ValidationReport:
        report = ValidationReport()
        seen_hashes: set[str] = set()
        intent_counter: Counter = Counter()
        tool_counter: Counter = Counter()
        known_tools = self._get_known_tools()

        for ex in dataset.examples:
            report.total += 1
            errors: list[str] = []

            if not ex.request or not ex.request.strip():
                errors.append("empty request")
                report.missing_fields.append({"error": "empty request", "record": ex.to_dict()})

            if ex.intent and ex.intent not in INTENT_CATEGORIES:
                errors.append(f"unknown intent: {ex.intent}")
                report.invalid_intents.append({"intent": ex.intent, "request": ex.request[:100]})

            for tool in ex.tools_used:
                if known_tools and tool not in known_tools:
                    errors.append(f"unknown tool: {tool}")
                    report.invalid_tools.append({"tool": tool, "request": ex.request[:100]})

            h = ex.content_hash
            if h in seen_hashes:
                errors.append("duplicate")
                report.duplicates.append({"request": ex.request[:100], "hash": h})
            seen_hashes.add(h)

            if errors:
                report.invalid += 1
            else:
                report.valid += 1

            intent_counter[ex.intent or "unknown"] += 1
            for t in ex.tools_used:
                tool_counter[t] += 1

        report.intent_distribution = dict(intent_counter)
        report.tool_distribution = dict(tool_counter)
        return report

    def _check_missing_fields(self, record: dict[str, Any]) -> list[str]:
        fields = REQUIRED_FIELDS_SYNTHETIC if "expected_tools" in record else REQUIRED_FIELDS
        missing: list[str] = []
        for f in fields:
            val = record.get(f)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(f)
        return missing

    def _check_intent(self, record: dict[str, Any], line_no: int, report: ValidationReport) -> bool:
        intent = record.get("intent", "")
        if intent and intent not in INTENT_CATEGORIES:
            report.invalid_intents.append({"line": line_no, "intent": intent, "request": str(record.get("request", ""))[:100]})
            return False
        return True

    def _check_tools(self, record: dict[str, Any], line_no: int, report: ValidationReport, known_tools: list[str]) -> bool:
        tools = record.get("expected_tools", [])
        if not tools:
            return True
        ok = True
        for tool in tools:
            if known_tools and tool not in known_tools:
                report.invalid_tools.append({"line": line_no, "tool": tool, "request": str(record.get("request", ""))[:100]})
                ok = False
        return ok

    def _check_duplicate(self, record: dict[str, Any], seen: set[str], line_no: int, report: ValidationReport) -> bool:
        raw = f"{record.get('request', '')}|{'|'.join(sorted(record.get('expected_tools', [])))}|{record.get('intent', '')}"
        import hashlib
        h = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if h in seen:
            report.duplicates.append({"line": line_no, "request": str(record.get("request", ""))[:100], "hash": h})
            return True
        seen.add(h)
        return False
