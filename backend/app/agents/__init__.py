"""AI agents for the knock-knock-AI content marketing pipeline.

Public API
----------
Base abstractions
    :class:`BaseAgent`  -- abstract base class for all agents.
    :class:`AgentContext` -- immutable input container.
    :class:`AgentResult` -- structured execution output.

Agents
    :class:`OrchestratorAgent` -- top-level pipeline supervisor.

Pipeline helpers
    :class:`PipelineStep` -- enum of ordered pipeline stages.
"""

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.orchestrator import OrchestratorAgent, PipelineStep

__all__ = [
    "AgentContext",
    "AgentResult",
    "BaseAgent",
    "OrchestratorAgent",
    "PipelineStep",
]
