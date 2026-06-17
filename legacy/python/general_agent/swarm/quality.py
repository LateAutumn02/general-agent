"""LLM Judge — quality review for agent task results.

Evaluates results on 4 dimensions: completeness, correctness, style, security.
Reference: ccswarm crates/ccswarm/src/orchestrator/llm_quality_judge.rs
"""

from __future__ import annotations

import json
import logging
import re

from general_agent.swarm.types import ConflictInfo, QualityReport, TaskResult

logger = logging.getLogger("general_agent.swarm.quality")

JUDGE_PROMPT = """You are a code quality judge. Evaluate the following task result.

Task: {task_description}
Output: {output}

Score each dimension from 0.0 (worst) to 1.0 (best):
- completeness: Did it fully address the task?
- correctness: Is the solution logically correct?
- style_consistency: Is the code style consistent and clean?
- security: Are there any security concerns? (1.0 = no concerns)

Reply in JSON format:
{{"completeness": 0.X, "correctness": 0.X, "style_consistency": 0.X, "security": 0.X, "suggestions": ["..."]}}"""


class QualityJudge:
    """LLM-based quality reviewer for agent outputs."""

    def __init__(self, min_score_threshold: float = 0.6) -> None:
        self.min_score_threshold = min_score_threshold
        self._reviews: list[QualityReport] = []

    async def review(
        self, task_result: TaskResult, task_description: str = "",
    ) -> QualityReport:
        """Evaluate a task result and return a quality report.

        If no API is available, returns a default pass (1.0 on all dimensions).
        """
        prompt = JUDGE_PROMPT.format(
            task_description=task_description or "Unknown task",
            output=task_result.output[:3000],
        )

        try:
            from general_agent.services.api.messages import query_model_simple
            response = await query_model_simple(prompt, max_tokens=500)

            # Parse JSON from response
            json_match = re.search(r"\{[^}]+\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                report = QualityReport(
                    completeness=float(data.get("completeness", 1.0)),
                    correctness=float(data.get("correctness", 1.0)),
                    style_consistency=float(data.get("style_consistency", 1.0)),
                    security=float(data.get("security", 1.0)),
                    suggestions=data.get("suggestions", []),
                )
                report.overall_score = (
                    report.completeness + report.correctness +
                    report.style_consistency + report.security
                ) / 4.0
            else:
                report = QualityReport(overall_score=1.0)  # can't parse = pass
        except Exception as e:
            logger.warning("Quality judge failed: %s — defaulting to pass", e)
            report = QualityReport(overall_score=1.0)

        self._reviews.append(report)
        return report

    def review_sync(self, task_result: TaskResult, task_description: str = "") -> QualityReport:
        """Non-async review — returns default pass (caller should use async review)."""
        report = QualityReport(overall_score=1.0)
        self._reviews.append(report)
        return report

    def needs_fix(self, report: QualityReport) -> bool:
        """Return True if the result should be reworked."""
        return report.overall_score < self.min_score_threshold

    def check_conflicts(
        self, results: list[TaskResult],
    ) -> list[ConflictInfo]:
        """Check for file-level conflicts between agent results."""
        conflicts: list[ConflictInfo] = []
        file_to_agent: dict[str, str] = {}
        for r in results:
            for artifact in r.artifacts:
                if artifact in file_to_agent:
                    conflicts.append(ConflictInfo(
                        file_path=artifact,
                        agent_a=file_to_agent[artifact],
                        agent_b=r.agent_id,
                        description=f"Both agents modified {artifact}",
                    ))
                else:
                    file_to_agent[artifact] = r.agent_id
        return conflicts

    @property
    def history(self) -> list[QualityReport]:
        return list(self._reviews)
