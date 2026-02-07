"""Tests for the Editor agent's quality gate logic."""

from __future__ import annotations

import pytest

from app.agents.editor import EditorAgent, SCORE_MIN_INDIVIDUAL, SCORE_MIN_AVERAGE


class TestQualityGate:
    """Test the static _check_quality_gate method."""

    def test_all_scores_pass(self):
        scores = {
            "readability_score": 85,
            "seo_score": 80,
            "ai_detection_score": 78,
            "factual_accuracy_score": 82,
            "brand_consistency_score": 79,
        }
        passed, failing = EditorAgent._check_quality_gate(scores)
        assert passed is True
        assert failing == []

    def test_one_score_below_individual_threshold(self):
        scores = {
            "readability_score": 90,
            "seo_score": 90,
            "ai_detection_score": 60,  # Below 70
            "factual_accuracy_score": 90,
            "brand_consistency_score": 90,
        }
        passed, failing = EditorAgent._check_quality_gate(scores)
        assert passed is False
        assert "ai_detection_score" in failing

    def test_average_below_threshold(self):
        scores = {
            "readability_score": 71,
            "seo_score": 71,
            "ai_detection_score": 71,
            "factual_accuracy_score": 71,
            "brand_consistency_score": 71,
        }
        # Average = 71, below 75
        passed, failing = EditorAgent._check_quality_gate(scores)
        assert passed is False
        # All dimensions flagged when average fails but individuals pass
        assert len(failing) == 5

    def test_boundary_values_pass(self):
        scores = {
            "readability_score": 75,
            "seo_score": 75,
            "ai_detection_score": 75,
            "factual_accuracy_score": 75,
            "brand_consistency_score": 75,
        }
        passed, failing = EditorAgent._check_quality_gate(scores)
        assert passed is True
        assert failing == []

    def test_multiple_failures(self):
        scores = {
            "readability_score": 50,
            "seo_score": 40,
            "ai_detection_score": 90,
            "factual_accuracy_score": 90,
            "brand_consistency_score": 90,
        }
        passed, failing = EditorAgent._check_quality_gate(scores)
        assert passed is False
        assert "readability_score" in failing
        assert "seo_score" in failing
