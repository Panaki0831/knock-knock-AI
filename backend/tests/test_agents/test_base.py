"""Tests for the BaseAgent abstraction."""

from __future__ import annotations

import pytest

from app.agents.base import AgentContext, AgentResult, BaseAgent


class DummyAgent(BaseAgent):
    """Minimal concrete agent for testing the base class."""

    @property
    def agent_name(self) -> str:
        return "dummy"

    @property
    def model_name(self) -> str:
        return "claude-sonnet-4-5-20250514"

    @property
    def system_prompt(self) -> str:
        return "You are a test agent."

    async def execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            success=True,
            output_data={"echo": context.input_data},
            tokens_used=0,
        )


def test_agent_context_immutability():
    ctx = AgentContext(task_id="test-1", input_data={"key": "value"})
    assert ctx.task_id == "test-1"
    assert ctx.input_data == {"key": "value"}
    assert ctx.article_id == ""
    assert ctx.metadata == {}


def test_agent_result_defaults():
    result = AgentResult(success=True)
    assert result.success is True
    assert result.output_data == {}
    assert result.error_message is None
    assert result.tokens_used == 0
    assert result.cost_usd == 0.0


def test_cost_estimation():
    cost = BaseAgent._estimate_cost(input_tokens=1_000_000, output_tokens=100_000)
    # $15/M input + $75/M output => $15 + $7.5 = $22.5
    assert abs(cost - 22.5) < 0.01


def test_text_from_response_mock():
    """Test the text extraction helper with a mock response object."""
    import types

    block = types.SimpleNamespace(type="text", text="Hello, world!")
    response = types.SimpleNamespace(content=[block])
    text = BaseAgent._text_from_response(response)
    assert text == "Hello, world!"


@pytest.mark.asyncio
async def test_dummy_agent_execute():
    agent = DummyAgent()
    ctx = AgentContext(task_id="t1", input_data={"foo": "bar"})
    result = await agent.execute(ctx)
    assert result.success is True
    assert result.output_data == {"echo": {"foo": "bar"}}


def test_agent_repr():
    agent = DummyAgent()
    assert "DummyAgent" in repr(agent)
    assert "dummy" in repr(agent)
