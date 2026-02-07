"""Base agent abstractions for the knock-knock-AI content marketing pipeline.

Every agent in the system inherits from :class:`BaseAgent` and communicates
via :class:`AgentContext` / :class:`AgentResult` value objects.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import anthropic
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Immutable bag of data handed to an agent at execution time.

    Attributes:
        task_id: Unique identifier for the current pipeline run / task.
        article_id: Identifier for the article being processed (may be empty
            for tasks that are not yet linked to a persisted article).
        input_data: Arbitrary input payload produced by the previous pipeline
            step or the initial trigger.
        metadata: Extra key-value pairs (locale, flags, caller info, ...).
    """

    task_id: str
    article_id: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentResult:
    """Structured output returned by every agent execution.

    Attributes:
        success: Whether the agent completed without error.
        output_data: The main payload produced by this agent.
        error_message: Human-readable description when ``success`` is False.
        tokens_used: Total token count (prompt + completion) for all LLM calls.
        cost_usd: Estimated cost in USD for the LLM usage.
        execution_time_seconds: Wall-clock duration of the ``execute`` call.
    """

    success: bool
    output_data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    execution_time_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Base agent
# ---------------------------------------------------------------------------


class BaseAgent(ABC):
    """Abstract base class for every AI agent in the pipeline.

    Subclasses **must** implement:

    * :pyattr:`agent_name`
    * :pyattr:`model_name`
    * :pyattr:`system_prompt`
    * :pymeth:`execute`

    The helper :pymeth:`_call_llm` wraps the Anthropic Messages API with
    structured logging, token tracking, and basic error handling so that
    subclasses can focus on prompt engineering rather than boiler-plate.
    """

    # --- abstract interface ---------------------------------------------------

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Short, unique identifier for this agent (e.g. ``'researcher'``)."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Anthropic model id to use (e.g. ``'claude-opus-4-5-20250213'``)."""

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System-level instruction given to the LLM on every call."""

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """Run the agent's core logic and return a structured result.

        Implementations should call :pymeth:`_call_llm` one or more times and
        aggregate the outputs into an :class:`AgentResult`.
        """

    # --- construction ---------------------------------------------------------

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._log = logger.bind(agent=self.agent_name)
        self._total_tokens: int = 0
        self._total_cost: float = 0.0

    # --- LLM helper -----------------------------------------------------------

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
    ) -> anthropic.types.Message:
        """Call the Anthropic Messages API with logging and token tracking.

        Parameters:
            messages: Conversation turns in the Messages-API format
                (``[{"role": "user", "content": "..."}, ...]``).
            max_tokens: Upper bound on the response length.
            temperature: Sampling temperature.
            stop_sequences: Optional early-stop strings.

        Returns:
            The raw :class:`anthropic.types.Message` from the API.

        Raises:
            anthropic.APIError: Re-raised after logging so the caller can
                decide how to handle it.
        """
        call_start = time.monotonic()
        self._log.info(
            "llm_call_start",
            model=self.model_name,
            message_count=len(messages),
            max_tokens=max_tokens,
            temperature=temperature,
        )

        try:
            kwargs: dict[str, Any] = {
                "model": self.model_name,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": self.system_prompt,
                "messages": messages,
            }
            if stop_sequences:
                kwargs["stop_sequences"] = stop_sequences

            response = await self._client.messages.create(**kwargs)

        except anthropic.APIError as exc:
            elapsed = time.monotonic() - call_start
            self._log.error(
                "llm_call_error",
                error_type=type(exc).__name__,
                error_message=str(exc),
                elapsed_seconds=round(elapsed, 3),
            )
            raise

        # --- bookkeeping ------------------------------------------------------
        elapsed = time.monotonic() - call_start
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = input_tokens + output_tokens

        cost = self._estimate_cost(input_tokens, output_tokens)

        self._total_tokens += total_tokens
        self._total_cost += cost

        self._log.info(
            "llm_call_complete",
            model=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=round(cost, 6),
            elapsed_seconds=round(elapsed, 3),
            stop_reason=response.stop_reason,
        )

        return response

    # --- cost estimation ------------------------------------------------------

    @staticmethod
    def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
        """Return a rough USD cost estimate.

        Prices are intentionally hard-coded as *approximate* catalogue rates so
        that the system can provide indicative costs without an external lookup.
        They should be reviewed when model pricing changes.
        """
        # Rates per 1 M tokens (as of early-2025 catalogue prices)
        INPUT_RATE = 15.0 / 1_000_000   # $15 / 1M input tokens (Opus-class)
        OUTPUT_RATE = 75.0 / 1_000_000  # $75 / 1M output tokens (Opus-class)
        return input_tokens * INPUT_RATE + output_tokens * OUTPUT_RATE

    # --- bookkeeping reset ----------------------------------------------------

    def _reset_token_tracking(self) -> None:
        """Zero out cumulative token / cost counters (call at execute start)."""
        self._total_tokens = 0
        self._total_cost = 0.0

    # --- convenience ----------------------------------------------------------

    @staticmethod
    def _text_from_response(response: anthropic.types.Message) -> str:
        """Extract the concatenated text content from an API response."""
        parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "\n".join(parts)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} agent_name={self.agent_name!r} model={self.model_name!r}>"
