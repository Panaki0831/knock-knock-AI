"""Tests for the Orchestrator agent's step resolution logic."""

from __future__ import annotations

from app.agents.orchestrator import OrchestratorAgent, PipelineStep


class TestResolveSteps:
    """Test the static _resolve_steps method."""

    def test_no_locales_skips_localize(self):
        entry = {"topic": "Test", "target_locales": []}
        steps = OrchestratorAgent._resolve_steps(entry)
        assert PipelineStep.LOCALIZE not in steps
        assert PipelineStep.RESEARCH in steps
        assert PipelineStep.PUBLISH in steps

    def test_with_locales_includes_localize(self):
        entry = {"topic": "Test", "target_locales": ["en", "id"]}
        steps = OrchestratorAgent._resolve_steps(entry)
        assert PipelineStep.LOCALIZE in steps

    def test_empty_string_locales_skips_localize(self):
        entry = {"topic": "Test", "target_locales": ["", " "]}
        steps = OrchestratorAgent._resolve_steps(entry)
        assert PipelineStep.LOCALIZE not in steps

    def test_no_locales_key_skips_localize(self):
        entry = {"topic": "Test"}
        steps = OrchestratorAgent._resolve_steps(entry)
        assert PipelineStep.LOCALIZE not in steps

    def test_step_order(self):
        entry = {"topic": "Test", "target_locales": ["en"]}
        steps = OrchestratorAgent._resolve_steps(entry)
        step_names = [s.value for s in steps]
        assert step_names == ["research", "plan", "write", "edit", "localize", "publish"]
