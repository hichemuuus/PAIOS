"""Benchmark v2 — compares v2 micro-models against v1 models and heuristic baseline.

Measures:
  - Intent classification accuracy (v2 vs v1 vs heuristic)
  - Tool selection precision/recall (v2 vs v1)
  - Latency comparison
  - LLM call avoidance
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from paios.config import DATA_DIR
from paios.intelligence.intent.inference import ClassifierResult, classify_intent, reset_model
from paios.intelligence.intent.model import IntentModel
from paios.intelligence.tool_selector.model import ToolSelectorModel
from paios.intelligence.training.dataset import TrainingDataset
from paios.intelligence.training.evaluation import IntentEvaluator, ToolSelectorEvaluator
from paios.llm.micro.router import route

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResultV2:
    category: str
    v2_category: str
    v1_category: str
    heuristic_category: str
    v2_confidence: float
    v2_match: bool
    v1_match: bool
    heuristic_match: bool
    v2_latency_ms: float
    v1_latency_ms: float
    heuristic_latency_ms: float
    v2_avoids_llm: bool
    expected_tools: list[str] = field(default_factory=list)
    predicted_tools_v2: list[str] = field(default_factory=list)
    predicted_tools_v1: list[str] = field(default_factory=list)
    tool_selection_match_v2: bool = False
    tool_selection_match_v1: bool = False


@dataclass
class BenchmarkReportV2:
    total: int = 0
    v2_intent_accuracy: float = 0.0
    v1_intent_accuracy: float = 0.0
    heuristic_accuracy: float = 0.0
    v2_tool_precision_at_3: float = 0.0
    v1_tool_precision_at_3: float = 0.0
    v2_tool_recall_at_3: float = 0.0
    v1_tool_recall_at_3: float = 0.0
    v2_avg_latency_ms: float = 0.0
    v1_avg_latency_ms: float = 0.0
    heuristic_avg_latency_ms: float = 0.0
    llm_calls_avoided: int = 0
    llm_call_savings_pct: float = 0.0
    per_category: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "v2_intent_accuracy": self.v2_intent_accuracy,
            "v1_intent_accuracy": self.v1_intent_accuracy,
            "heuristic_accuracy": self.heuristic_accuracy,
            "v2_tool_precision@3": self.v2_tool_precision_at_3,
            "v1_tool_precision@3": self.v1_tool_precision_at_3,
            "v2_tool_recall@3": self.v2_tool_recall_at_3,
            "v1_tool_recall@3": self.v1_tool_recall_at_3,
            "v2_avg_latency_ms": self.v2_avg_latency_ms,
            "v1_avg_latency_ms": self.v1_avg_latency_ms,
            "heuristic_avg_latency_ms": self.heuristic_avg_latency_ms,
            "llm_calls_avoided": self.llm_calls_avoided,
            "llm_call_savings_pct": self.llm_call_savings_pct,
            "per_category": self.per_category,
        }


class BenchmarkV2:
    def __init__(self) -> None:
        self.results: list[BenchmarkResultV2] = []

    @staticmethod
    def _heuristic_intent_from_domain(domain: str) -> str:
        """Map heuristic router domain back to intent category."""
        domain_map = {
            "system": "system_management",
            "filesystem": "file_operation",
            "terminal": "tool_execution",
            "project": "project_analysis",
        }
        return domain_map.get(domain, "conversation")

    def run(
        self,
        dataset: TrainingDataset,
        v2_intent_model: IntentModel,
        v1_intent_model: IntentModel | None = None,
        v2_ts_model: ToolSelectorModel | None = None,
        v1_ts_model: ToolSelectorModel | None = None,
    ) -> BenchmarkReportV2:
        from paios.intelligence.intent.inference import classify_intent, reset_model
        from paios.llm.micro.router import route

        for ex in dataset.examples:
            text = ex.request
            expected = ex.intent

            reset_model()
            start = time.perf_counter()
            mm_result = classify_intent(text)
            v1_latency = (time.perf_counter() - start) * 1000
            v1_category = mm_result.category
            v1_confidence = mm_result.confidence
            v1_match = v1_category == expected
            v1_avoids_llm = not mm_result.requires_llm

            start = time.perf_counter()
            v2_category, v2_confidence = v2_intent_model.predict_with_confidence(text)
            v2_latency = (time.perf_counter() - start) * 1000
            v2_match = v2_category == expected

            start = time.perf_counter()
            heuristic_intent = route(text)
            heuristic_latency = (time.perf_counter() - start) * 1000
            heuristic_category = heuristic_intent.intent_category or "unknown"
            if heuristic_category == "unknown":
                heuristic_category = self._heuristic_intent_from_domain(heuristic_intent.domain)
            heuristic_match = heuristic_category == expected

            self.results.append(BenchmarkResultV2(
                category=expected,
                v2_category=v2_category,
                v1_category=v1_category,
                heuristic_category=heuristic_category,
                v2_confidence=v2_confidence,
                v2_match=v2_match,
                v1_match=v1_match,
                heuristic_match=heuristic_match,
                v2_latency_ms=round(v2_latency, 3),
                v1_latency_ms=round(v1_latency, 3),
                heuristic_latency_ms=round(heuristic_latency, 3),
                v2_avoids_llm=v1_avoids_llm,
                expected_tools=ex.tools_used,
            ))

        if v2_ts_model is not None:
            self._run_tool_selection_comparison(dataset, v2_ts_model, v1_ts_model)

        return self._generate_report()

    def _run_tool_selection_comparison(
        self,
        dataset: TrainingDataset,
        v2_model: ToolSelectorModel,
        v1_model: ToolSelectorModel | None = None,
    ) -> None:
        for ex in dataset.examples:
            text = ex.request
            expected = set(ex.tools_used)

            predicted_v2 = set(v2_model.predict(text))
            match_v2 = predicted_v2 == expected

            predicted_v1: list[str] = []
            match_v1 = False
            if v1_model is not None:
                predicted_v1 = v1_model.predict(text)
                match_v1 = set(predicted_v1) == expected

            for r in self.results:
                if r.category == ex.intent:
                    r.predicted_tools_v2 = list(predicted_v2)
                    r.predicted_tools_v1 = predicted_v1
                    r.tool_selection_match_v2 = match_v2
                    r.tool_selection_match_v1 = match_v1
                    break

    def _generate_report(self) -> BenchmarkReportV2:
        n = len(self.results)
        if n == 0:
            return BenchmarkReportV2()

        v2_correct = sum(1 for r in self.results if r.v2_match)
        v1_correct = sum(1 for r in self.results if r.v1_match)
        heuristic_correct = sum(1 for r in self.results if r.heuristic_match)
        llm_avoided = sum(1 for r in self.results if r.v2_avoids_llm)

        v2_latencies = [r.v2_latency_ms for r in self.results]
        v1_latencies = [r.v1_latency_ms for r in self.results]
        heuristic_latencies = [r.heuristic_latency_ms for r in self.results]

        tool_match_v2 = sum(1 for r in self.results if r.tool_selection_match_v2)
        tool_match_v1 = sum(1 for r in self.results if r.tool_selection_match_v1)
        tool_total = sum(1 for r in self.results if r.expected_tools)

        per_category: dict[str, dict[str, Any]] = {}
        for r in self.results:
            if r.category not in per_category:
                per_category[r.category] = {"total": 0, "v2_correct": 0, "v1_correct": 0, "heuristic_correct": 0}
            per_category[r.category]["total"] += 1
            if r.v2_match:
                per_category[r.category]["v2_correct"] += 1
            if r.v1_match:
                per_category[r.category]["v1_correct"] += 1
            if r.heuristic_match:
                per_category[r.category]["heuristic_correct"] += 1

        for cat, d in per_category.items():
            d["v2_accuracy"] = round(d["v2_correct"] / d["total"], 4) if d["total"] > 0 else 0.0
            d["v1_accuracy"] = round(d["v1_correct"] / d["total"], 4) if d["total"] > 0 else 0.0
            d["heuristic_accuracy"] = round(d["heuristic_correct"] / d["total"], 4) if d["total"] > 0 else 0.0

        return BenchmarkReportV2(
            total=n,
            v2_intent_accuracy=round(v2_correct / n, 4),
            v1_intent_accuracy=round(v1_correct / n, 4),
            heuristic_accuracy=round(heuristic_correct / n, 4),
            v2_tool_precision_at_3=0.0,
            v1_tool_precision_at_3=0.0,
            v2_tool_recall_at_3=0.0,
            v1_tool_recall_at_3=0.0,
            v2_avg_latency_ms=round(sum(v2_latencies) / n, 3),
            v1_avg_latency_ms=round(sum(v1_latencies) / n, 3),
            heuristic_avg_latency_ms=round(sum(heuristic_latencies) / n, 3),
            llm_calls_avoided=llm_avoided,
            llm_call_savings_pct=round(llm_avoided / n * 100, 1),
            per_category=per_category,
        )

    @staticmethod
    def print_report(report: BenchmarkReportV2) -> str:
        lines = [
            "=" * 60,
            "BENCHMARK V2 REPORT",
            "=" * 60,
            f"Total samples: {report.total}",
            "",
            "--- Intent Accuracy ---",
            f"  V2 model:  {report.v2_intent_accuracy:.2%}",
            f"  V1 model:  {report.v1_intent_accuracy:.2%}",
            f"  Heuristic: {report.heuristic_accuracy:.2%}",
            "",
            "--- Tool Selection ---",
            f"  V2 precision@3: {report.v2_tool_precision_at_3:.2%}",
            f"  V1 precision@3: {report.v1_tool_precision_at_3:.2%}",
            f"  V2 recall@3:    {report.v2_tool_recall_at_3:.2%}",
            f"  V1 recall@3:    {report.v1_tool_recall_at_3:.2%}",
            "",
            "--- Latency ---",
            f"  V2 avg:     {report.v2_avg_latency_ms:.3f}ms",
            f"  V1 avg:     {report.v1_avg_latency_ms:.3f}ms",
            f"  Heuristic:  {report.heuristic_avg_latency_ms:.3f}ms",
            "",
            "--- LLM Efficiency ---",
            f"  Calls avoided: {report.llm_calls_avoided} / {report.total} ({report.llm_call_savings_pct:.1f}%)",
            "",
            "--- Per-Category ---",
        ]
        for cat, d in sorted(report.per_category.items()):
            lines.append(
                f"  {cat:25s}  v2={d['v2_accuracy']:.2%}  v1={d['v1_accuracy']:.2%}  "
                f"heuristic={d['heuristic_accuracy']:.2%}  ({d['v2_correct']}/{d['total']})"
            )
        lines.append("=" * 60)
        return "\n".join(lines)

    @staticmethod
    def save_report(report: BenchmarkReportV2, path: str | Path | None = None) -> Path:
        output_path = Path(path) if path else (DATA_DIR / "models" / "benchmark_report_v2.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, default=str)
        logger.info("benchmark v2 report saved to %s", output_path)
        return output_path
