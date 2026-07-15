"""Quality scoring for training examples.

Assigns a 0.0–1.0 quality score to each collected example based on:
- Task completion status
- Efficiency (retries vs steps)
- Tool call diversity and success rate
- Duration reasonableness
- Recency (newer examples weighted higher)
- User feedback when available
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    overall: float = 0.0
    completion_bonus: float = 0.0
    efficiency_score: float = 0.0
    tool_diversity_score: float = 0.0
    duration_penalty: float = 0.0
    retry_penalty: float = 0.0
    recency_bonus: float = 0.0
    feedback_bonus: float = 0.0


class QualityScorer:
    def score(self, example: dict[str, Any]) -> QualityScore:
        completion_bonus = 1.0 if example.get("success") else 0.0

        total_steps = example.get("total_steps", 0) or 1
        retry_count = example.get("retry_count", 0)
        efficiency_score = max(0.0, 1.0 - (retry_count / max(total_steps, 1)))

        tools = example.get("tools_used", [])
        unique_tools = len(set(tools))
        tool_diversity_score = min(1.0, unique_tools / 3.0)

        duration_ms = example.get("duration_ms", 0)
        expected_per_step = 2000
        max_reasonable = max(1000, total_steps * expected_per_step * 3)
        duration_penalty = 0.0
        if duration_ms > max_reasonable and duration_ms > 0:
            ratio = duration_ms / max_reasonable
            duration_penalty = min(0.5, (ratio - 1.0) * 0.1)

        retry_penalty = min(0.5, retry_count * 0.1)

        recency_bonus = 0.0
        timestamp = example.get("timestamp")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                age_hours = (datetime.now(UTC) - dt).total_seconds() / 3600
                recency_bonus = max(0.0, 1.0 - age_hours / 720)
            except (ValueError, TypeError):
                pass

        feedback_bonus = 0.0
        feedback_score = example.get("feedback_score")
        if feedback_score is not None:
            feedback_bonus = feedback_score * 0.3

        overall = (
            completion_bonus * 0.30
            + efficiency_score * 0.20
            + tool_diversity_score * 0.10
            + recency_bonus * 0.10
            + feedback_bonus
            - duration_penalty * 0.15
            - retry_penalty * 0.10
        )
        overall = max(0.0, min(1.0, overall))

        return QualityScore(
            overall=round(overall, 4),
            completion_bonus=completion_bonus,
            efficiency_score=round(efficiency_score, 4),
            tool_diversity_score=round(tool_diversity_score, 4),
            duration_penalty=round(duration_penalty, 4),
            retry_penalty=round(retry_penalty, 4),
            recency_bonus=round(recency_bonus, 4),
            feedback_bonus=round(feedback_bonus, 4),
        )
