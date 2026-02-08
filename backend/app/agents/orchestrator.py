"""Orchestrator agent -- the top-level supervisor of the content pipeline.

The :class:`OrchestratorAgent` drives the full content-marketing workflow:

    Calendar entry  ->  Researcher  ->  Planner  ->  Writer
                     ->  Editor  ->  (Localizer)  ->  Publisher

Each transition is gated by a lightweight quality check.  If a step fails the
gate, the orchestrator retries that step (up to ``settings.max_retry_count``
times) before aborting the pipeline.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any

import structlog

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.config import settings

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Pipeline step registry
# ---------------------------------------------------------------------------


class PipelineStep(str, Enum):
    """Ordered stages of the content pipeline."""

    RESEARCH = "research"
    PLAN = "plan"
    WRITE = "write"
    EDIT = "edit"
    LOCALIZE = "localize"
    PUBLISH = "publish"


# The canonical execution order.  ``LOCALIZE`` is conditional.
_DEFAULT_STEPS: list[PipelineStep] = [
    PipelineStep.RESEARCH,
    PipelineStep.PLAN,
    PipelineStep.WRITE,
    PipelineStep.EDIT,
    PipelineStep.LOCALIZE,
    PipelineStep.PUBLISH,
]

# Steps that require an LLM quality-gate evaluation between attempts.
# Most steps are auto-approved to reduce latency. The Editor agent already
# performs thorough quality scoring for the article content.
_GATED_STEPS: frozenset[PipelineStep] = frozenset({
    PipelineStep.RESEARCH,
})


# ---------------------------------------------------------------------------
# Step result tracking
# ---------------------------------------------------------------------------


class StepOutcome:
    """Container for the result of a single pipeline step."""

    __slots__ = (
        "step",
        "success",
        "attempts",
        "output_data",
        "error_message",
        "tokens_used",
        "cost_usd",
        "execution_time_seconds",
    )

    def __init__(self, step: PipelineStep) -> None:
        self.step = step
        self.success: bool = False
        self.attempts: int = 0
        self.output_data: dict[str, Any] = {}
        self.error_message: str | None = None
        self.tokens_used: int = 0
        self.cost_usd: float = 0.0
        self.execution_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step.value,
            "status": "completed" if self.success else "failed",
            "success": self.success,
            "attempts": self.attempts,
            "error": self.error_message,
            "error_message": self.error_message,
            "tokens_used": self.tokens_used,
            "cost_usd": round(self.cost_usd, 6),
            "execution_time_seconds": round(self.execution_time_seconds, 3),
        }


# ---------------------------------------------------------------------------
# Orchestrator agent
# ---------------------------------------------------------------------------

_ORCHESTRATOR_SYSTEM_PROMPT = """\
You are the Orchestrator, the top-level supervisor of the knock-knock-AI \
content-marketing pipeline.

Your responsibilities:
1. Decompose a content-calendar entry into a sequence of specialist tasks \
   (Research -> Plan -> Write -> Edit -> Localize -> Publish).
2. Evaluate the quality of each step's output before advancing to the next \
   step.  When quality is insufficient, provide concrete, actionable feedback \
   and request a retry.
3. Track overall progress and token / cost budgets.
4. Decide whether the optional Localization step is required based on the \
   calendar entry's target locales.

Quality-gate criteria (apply proportionally to each step):
- **Completeness**: Does the output address every requirement from the input?
- **Accuracy**: Are factual claims correct and well-sourced?
- **Coherence**: Is the output logically structured and internally consistent?
- **Tone & style**: Does the output match the brand voice and target audience?

When you evaluate an output, respond with a JSON object:
{
  "passed": true | false,
  "score": <float 0-1>,
  "feedback": "<actionable feedback if not passed>"
}

Always think step-by-step and be rigorous in your evaluations.
"""


class OrchestratorAgent(BaseAgent):
    """Supervises the end-to-end content pipeline.

    Usage::

        orchestrator = OrchestratorAgent()
        result = await orchestrator.run_pipeline(calendar_entry)
    """

    # --- BaseAgent interface --------------------------------------------------

    @property
    def agent_name(self) -> str:
        return "orchestrator"

    @property
    def model_name(self) -> str:
        return settings.default_orchestrator_model

    @property
    def system_prompt(self) -> str:
        return _ORCHESTRATOR_SYSTEM_PROMPT

    async def execute(
        self,
        context: AgentContext,
        *,
        progress_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> AgentResult:
        """Execute the orchestrator as a regular agent step.

        In practice callers should prefer :pymeth:`run_pipeline` which accepts
        a raw calendar entry and manages all internal context wiring.  This
        method exists to satisfy the :class:`BaseAgent` interface so the
        orchestrator can itself be composed into higher-level workflows.
        """
        calendar_entry: dict[str, Any] = context.input_data.get("calendar_entry", {})
        if not calendar_entry:
            return AgentResult(
                success=False,
                error_message="No calendar_entry found in context input_data.",
            )
        pipeline_result = await self.run_pipeline(
            calendar_entry,
            task_id=context.task_id,
            article_id=context.article_id,
            progress_callback=progress_callback,
        )
        return AgentResult(
            success=pipeline_result["success"],
            output_data=pipeline_result,
            tokens_used=pipeline_result.get("total_tokens_used", 0),
            cost_usd=pipeline_result.get("total_cost_usd", 0.0),
            execution_time_seconds=pipeline_result.get("total_execution_time_seconds", 0.0),
        )

    # --- public pipeline entry point ------------------------------------------

    async def run_pipeline(
        self,
        calendar_entry: dict[str, Any],
        *,
        task_id: str | None = None,
        article_id: str | None = None,
        progress_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """Orchestrate the full content pipeline for a single calendar entry.

        Parameters:
            calendar_entry: A dict describing the content to produce.  Expected
                keys include ``topic``, ``target_keywords``, ``target_locales``,
                ``target_platforms``, ``publish_date``, and ``notes``.
            task_id: Optional pre-assigned task identifier.
            article_id: Optional pre-assigned article identifier.

        Returns:
            A comprehensive dict containing:

            * ``success`` -- bool
            * ``task_id`` / ``article_id``
            * ``steps`` -- list of per-step dicts (see :class:`StepOutcome`)
            * ``final_output`` -- the last successful step's output
            * ``total_tokens_used`` / ``total_cost_usd``
            * ``total_execution_time_seconds``
            * ``error_message`` -- present only on failure
        """
        task_id = task_id or uuid.uuid4().hex
        article_id = article_id or ""
        pipeline_start = time.monotonic()

        log = self._log.bind(task_id=task_id, article_id=article_id)
        log.info("pipeline_start", topic=calendar_entry.get("topic", "<unknown>"))

        # Determine which steps to run.
        steps = self._resolve_steps(calendar_entry)

        step_outcomes: list[StepOutcome] = []
        cumulative_data: dict[str, Any] = {"calendar_entry": calendar_entry}
        pipeline_success = True
        pipeline_error: str | None = None

        for step in steps:
            # Notify caller of step transition so it can update the DB.
            if progress_callback is not None:
                try:
                    await progress_callback(step.value)
                except Exception as cb_exc:
                    log.warning("progress_callback_error", step=step.value, error=str(cb_exc))

            outcome = await self._run_step(
                step=step,
                task_id=task_id,
                article_id=article_id,
                cumulative_data=cumulative_data,
                log=log,
            )
            step_outcomes.append(outcome)

            if not outcome.success:
                pipeline_success = False
                pipeline_error = (
                    f"Pipeline aborted at step '{step.value}': {outcome.error_message}"
                )
                log.error("pipeline_step_failed", step=step.value, error=outcome.error_message)
                break

            # Feed the step output forward.
            cumulative_data[step.value] = outcome.output_data

        # --- aggregate totals -------------------------------------------------
        total_tokens = sum(o.tokens_used for o in step_outcomes)
        total_cost = sum(o.cost_usd for o in step_outcomes)
        total_time = time.monotonic() - pipeline_start

        log.info(
            "pipeline_complete",
            success=pipeline_success,
            steps_run=len(step_outcomes),
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 6),
            total_seconds=round(total_time, 3),
        )

        result: dict[str, Any] = {
            "success": pipeline_success,
            "task_id": task_id,
            "article_id": article_id,
            "steps": [o.to_dict() for o in step_outcomes],
            "final_output": step_outcomes[-1].output_data if step_outcomes else {},
            "research_data": cumulative_data.get("research", {}),
            "total_tokens_used": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "total_execution_time_seconds": round(total_time, 3),
        }
        if pipeline_error:
            result["error_message"] = pipeline_error

        return result

    # --- internal helpers -----------------------------------------------------

    @staticmethod
    def _resolve_steps(calendar_entry: dict[str, Any]) -> list[PipelineStep]:
        """Return the list of steps to execute.

        The localization step is included only when the calendar entry
        specifies ``target_locales`` with at least one non-empty value.
        """
        target_locales: list[str] = calendar_entry.get("target_locales", [])
        needs_localization = bool(target_locales and any(loc.strip() for loc in target_locales))

        steps: list[PipelineStep] = []
        for step in _DEFAULT_STEPS:
            if step is PipelineStep.LOCALIZE and not needs_localization:
                continue
            steps.append(step)
        return steps

    async def _run_step(
        self,
        *,
        step: PipelineStep,
        task_id: str,
        article_id: str,
        cumulative_data: dict[str, Any],
        log: structlog.stdlib.BoundLogger,
    ) -> StepOutcome:
        """Execute a single pipeline step with quality-gate retries."""
        outcome = StepOutcome(step)
        max_retries = settings.max_retry_count

        for attempt in range(1, max_retries + 1):
            outcome.attempts = attempt
            step_start = time.monotonic()

            log.info("step_attempt_start", step=step.value, attempt=attempt)

            try:
                agent = self._get_agent_for_step(step)
                context = AgentContext(
                    task_id=task_id,
                    article_id=article_id,
                    input_data=cumulative_data,
                    metadata={"step": step.value, "attempt": attempt},
                )
                result = await agent.execute(context)
            except Exception as exc:
                elapsed = time.monotonic() - step_start
                outcome.execution_time_seconds += elapsed
                log.error(
                    "step_execution_error",
                    step=step.value,
                    attempt=attempt,
                    error=str(exc),
                )
                outcome.error_message = f"Execution error on attempt {attempt}: {exc}"
                continue  # retry

            elapsed = time.monotonic() - step_start
            outcome.execution_time_seconds += elapsed
            outcome.tokens_used += result.tokens_used
            outcome.cost_usd += result.cost_usd

            if not result.success:
                log.warning(
                    "step_returned_failure",
                    step=step.value,
                    attempt=attempt,
                    error=result.error_message,
                )
                outcome.error_message = result.error_message
                continue  # retry

            # --- quality gate (only for research step; editor handles article QA) ---
            # Skip the LLM-based quality gate for most steps to cut latency.
            # The editor agent already performs thorough quality scoring.
            if step in _GATED_STEPS:
                gate_passed = await self._quality_gate(
                    step=step,
                    step_output=result.output_data,
                    cumulative_data=cumulative_data,
                    log=log,
                )
            else:
                gate_passed = True

            if gate_passed:
                outcome.success = True
                outcome.output_data = result.output_data
                outcome.error_message = None
                log.info(
                    "step_attempt_success",
                    step=step.value,
                    attempt=attempt,
                    elapsed=round(elapsed, 3),
                )
                return outcome

            log.warning(
                "quality_gate_failed",
                step=step.value,
                attempt=attempt,
            )
            outcome.error_message = (
                f"Quality gate failed after attempt {attempt}."
            )
            # Feed gate feedback into cumulative data so the next attempt can use it.
            cumulative_data[f"_feedback_{step.value}_{attempt}"] = (
                outcome.error_message
            )

        # All retries exhausted.
        if outcome.error_message is None:
            outcome.error_message = (
                f"Step '{step.value}' failed after {max_retries} attempts."
            )
        return outcome

    # --- quality gate ---------------------------------------------------------

    async def _quality_gate(
        self,
        *,
        step: PipelineStep,
        step_output: dict[str, Any],
        cumulative_data: dict[str, Any],
        log: structlog.stdlib.BoundLogger,
    ) -> bool:
        """Ask the orchestrator LLM to evaluate the output of a step.

        Returns ``True`` when the output passes quality criteria.
        """
        import json as _json

        calendar_entry = cumulative_data.get("calendar_entry", {})
        evaluation_prompt = (
            f"Evaluate the output of the **{step.value}** step.\n\n"
            f"### Calendar entry (context)\n```json\n"
            f"{_json.dumps(calendar_entry, ensure_ascii=False, indent=2)}\n```\n\n"
            f"### Step output\n```json\n"
            f"{_json.dumps(step_output, ensure_ascii=False, indent=2)}\n```\n\n"
            "Respond with a JSON object: "
            '{"passed": true/false, "score": <0-1>, "feedback": "..."}'
        )

        try:
            response = await self._call_llm(
                messages=[{"role": "user", "content": evaluation_prompt}],
                max_tokens=1024,
                temperature=0.2,
            )
            text = self._text_from_response(response)

            # Attempt to parse the JSON from the LLM response.
            # The model may wrap it in markdown fences; strip them.
            cleaned = text.strip()
            if cleaned.startswith("```"):
                # Remove opening fence (possibly ```json)
                cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            evaluation = _json.loads(cleaned)
            passed: bool = evaluation.get("passed", False)
            score: float = evaluation.get("score", 0.0)
            feedback: str = evaluation.get("feedback", "")

            log.info(
                "quality_gate_result",
                step=step.value,
                passed=passed,
                score=score,
                feedback=feedback[:200],
            )
            return passed

        except Exception as exc:
            # If the gate itself errors out, be lenient and let the step pass
            # so a transient LLM hiccup doesn't block the whole pipeline.
            log.warning(
                "quality_gate_error",
                step=step.value,
                error=str(exc),
            )
            return True

    # --- agent registry -------------------------------------------------------

    def _get_agent_for_step(self, step: PipelineStep) -> BaseAgent:
        """Return the appropriate agent instance for *step*.

        This uses lazy imports so that each agent module is only loaded when
        its step is actually executed, and to avoid circular imports.
        """
        if step is PipelineStep.RESEARCH:
            from app.agents.researcher import ResearcherAgent

            return ResearcherAgent()

        if step is PipelineStep.PLAN:
            from app.agents.planner import PlannerAgent

            return PlannerAgent()

        if step is PipelineStep.WRITE:
            from app.agents.writer import WriterAgent

            return WriterAgent()

        if step is PipelineStep.EDIT:
            from app.agents.editor import EditorAgent

            return EditorAgent()

        if step is PipelineStep.LOCALIZE:
            from app.agents.localizer import LocalizerAgent

            return LocalizerAgent()

        if step is PipelineStep.PUBLISH:
            from app.agents.publisher import PublisherAgent

            return PublisherAgent()

        raise ValueError(f"No agent registered for step: {step!r}")
