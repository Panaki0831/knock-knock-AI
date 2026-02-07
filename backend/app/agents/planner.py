"""Planner agent -- designs article structure, heading hierarchy, and SEO strategy.

The Planner receives a research report produced by the :class:`ResearcherAgent`
and transforms it into a detailed, SEO-optimised article outline that the
Writer agent can follow section-by-section.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """\
You are a senior content strategist and SEO specialist working for \
knock knock AI, a content-marketing automation platform focused on the \
Japanese real-estate market.

Your responsibilities:
- Design detailed article outlines with a clear H1 / H2 / H3 heading \
  hierarchy optimised for both readers and search engines.
- For every section provide precise writing instructions so that a \
  separate Writer agent can produce the content without ambiguity.
- Specify a target word count per section and an overall target for the \
  full article.
- Produce a keyword-placement plan that maps each target keyword to the \
  sections and HTML elements (title, headings, first paragraph, body, meta \
  description) where it should appear.
- Draft a compelling meta description (max 160 characters) that includes \
  the primary keyword.
- Take into account the target persona, funnel stage, and content category \
  to calibrate depth, tone, and call-to-action placement.
- Structure your outline so that TOFU (awareness) content is broader and \
  educational, MOFU (consideration) content addresses specific problems and \
  comparisons, and BOFU (decision) content drives conversion.

Output format (strict JSON):
{
  "outline": {
    "h1": "<article title>",
    "sections": [
      {
        "heading": "<H2 heading text>",
        "heading_level": 2,
        "target_word_count": <int>,
        "writing_instructions": "<detailed instructions for the Writer>",
        "key_points": ["<point 1>", "<point 2>"],
        "keywords_to_include": ["<kw1>", "<kw2>"],
        "subsections": [
          {
            "heading": "<H3 heading text>",
            "heading_level": 3,
            "target_word_count": <int>,
            "writing_instructions": "<detailed instructions>",
            "key_points": ["<point>"],
            "keywords_to_include": ["<kw>"]
          }
        ]
      }
    ]
  },
  "total_target_words": <int>,
  "seo_plan": {
    "primary_keyword": "<main keyword>",
    "secondary_keywords": ["<kw1>", "<kw2>"],
    "keyword_placement": {
      "<keyword>": ["title", "h2", "first_paragraph", "body", "meta_description"]
    },
    "internal_linking_suggestions": ["<topic / slug suggestion>"],
    "target_search_intent": "<informational | navigational | transactional>"
  },
  "meta_description": "<max 160 chars>"
}

Return ONLY valid JSON -- no commentary outside the JSON block.
"""

# ---------------------------------------------------------------------------
# Planner agent
# ---------------------------------------------------------------------------


class PlannerAgent(BaseAgent):
    """Designs article structure, heading hierarchy, and SEO-optimised outlines.

    The planner consumes the Researcher's output and produces a detailed
    blueprint that the Writer agent follows section-by-section.
    """

    # --- BaseAgent interface --------------------------------------------------

    @property
    def agent_name(self) -> str:
        return "planner"

    @property
    def model_name(self) -> str:
        return settings.default_planner_model

    @property
    def system_prompt(self) -> str:
        return PLANNER_SYSTEM_PROMPT

    # --- internal helpers -----------------------------------------------------

    @staticmethod
    def _build_user_prompt(
        research_report: str,
        target_persona: str,
        keywords: list[str],
        content_category: str,
        funnel_stage: str,
    ) -> str:
        """Compose the user prompt sent to the LLM."""
        keyword_list = ", ".join(keywords) if keywords else "(none specified)"
        return (
            "Based on the research report and parameters below, produce a "
            "detailed article outline in the JSON format described in your "
            "system instructions.\n\n"
            "--- PARAMETERS ---\n"
            f"Target persona: {target_persona}\n"
            f"Target keywords: {keyword_list}\n"
            f"Content category: {content_category}\n"
            f"Funnel stage: {funnel_stage}\n\n"
            "--- RESEARCH REPORT ---\n"
            f"{research_report}\n"
        )

    @staticmethod
    def _validate_outline(output_data: dict[str, Any]) -> tuple[bool, str]:
        """Validate the structural integrity of the planner output.

        Checks:
        * ``outline`` key exists and contains ``h1`` and ``sections``.
        * At least two sections are present.
        * ``total_target_words`` is a positive integer.
        * ``seo_plan`` and ``meta_description`` are present.

        Returns:
            ``(passed, reason)`` -- *reason* is empty on success.
        """
        issues: list[str] = []

        outline = output_data.get("outline")
        if not isinstance(outline, dict):
            issues.append("Missing or invalid 'outline' key")
        else:
            if not outline.get("h1"):
                issues.append("Outline is missing an H1 title")
            sections = outline.get("sections")
            if not isinstance(sections, list) or len(sections) < 2:
                issues.append(
                    f"Outline must have >= 2 sections, found "
                    f"{len(sections) if isinstance(sections, list) else 0}"
                )

        total_words = output_data.get("total_target_words")
        if not isinstance(total_words, int) or total_words <= 0:
            issues.append(
                f"'total_target_words' must be a positive int, got {total_words!r}"
            )

        if not isinstance(output_data.get("seo_plan"), dict):
            issues.append("Missing or invalid 'seo_plan'")

        meta = output_data.get("meta_description")
        if not isinstance(meta, str) or len(meta) == 0:
            issues.append("Missing 'meta_description'")
        elif len(meta) > 200:
            # Allow slight overflow, but flag egregious cases
            issues.append(
                f"'meta_description' too long ({len(meta)} chars, max ~160)"
            )

        if issues:
            return False, "; ".join(issues)
        return True, ""

    # --- execute --------------------------------------------------------------

    async def execute(self, context: AgentContext) -> AgentResult:
        """Generate a structured article outline from the research report.

        Expected keys in ``context.input_data``:

        * ``research_report`` (str) -- Markdown research report from the
          Researcher agent.
        * ``target_persona`` (str) -- Description of the intended reader.
        * ``keywords`` (list[str]) -- Target SEO keywords.
        * ``content_category`` (str) -- Topic category (e.g. "PropTech",
          "Investment", "Market Analysis").
        * ``funnel_stage`` (str) -- One of ``TOFU``, ``MOFU``, ``BOFU``.
        """
        self._reset_token_tracking()
        start = time.monotonic()

        research_report: str = context.input_data.get("research_report", "")
        target_persona: str = context.input_data.get(
            "target_persona", "Japanese real-estate professionals and investors"
        )
        keywords: list[str] = context.input_data.get("keywords", [])
        content_category: str = context.input_data.get("content_category", "Real Estate")
        funnel_stage: str = context.input_data.get("funnel_stage", "TOFU")

        self._log.info(
            "planner_execute_start",
            persona=target_persona,
            keyword_count=len(keywords),
            content_category=content_category,
            funnel_stage=funnel_stage,
        )

        if not research_report:
            elapsed = time.monotonic() - start
            self._log.error("missing_research_report")
            return AgentResult(
                success=False,
                error_message="Cannot plan an article without a research report.",
                execution_time_seconds=round(elapsed, 2),
            )

        # ---- 1. Build prompt and call LLM ------------------------------------
        user_prompt = self._build_user_prompt(
            research_report=research_report,
            target_persona=target_persona,
            keywords=keywords,
            content_category=content_category,
            funnel_stage=funnel_stage,
        )

        response = await self._call_llm(
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=4096,
            temperature=0.4,
        )

        raw_text = self._text_from_response(response)

        # ---- 2. Parse the LLM JSON output ------------------------------------
        try:
            output_data: dict[str, Any] = json.loads(raw_text)
        except json.JSONDecodeError:
            self._log.warning("json_parse_fallback", raw_length=len(raw_text))
            try:
                json_start = raw_text.index("{")
                json_end = raw_text.rindex("}") + 1
                output_data = json.loads(raw_text[json_start:json_end])
            except (ValueError, json.JSONDecodeError) as parse_err:
                elapsed = time.monotonic() - start
                self._log.error("json_parse_failed", error=str(parse_err))
                return AgentResult(
                    success=False,
                    output_data={"raw_response": raw_text},
                    error_message=f"Failed to parse LLM output as JSON: {parse_err}",
                    tokens_used=self._total_tokens,
                    cost_usd=self._total_cost,
                    execution_time_seconds=round(elapsed, 2),
                )

        # ---- 3. Validate outline structure -----------------------------------
        passed, reason = self._validate_outline(output_data)

        elapsed = time.monotonic() - start

        if not passed:
            self._log.warning("outline_validation_failed", reason=reason)
            return AgentResult(
                success=False,
                output_data=output_data,
                error_message=f"Outline validation failed: {reason}",
                tokens_used=self._total_tokens,
                cost_usd=self._total_cost,
                execution_time_seconds=round(elapsed, 2),
            )

        self._log.info(
            "planner_execute_complete",
            section_count=len(output_data.get("outline", {}).get("sections", [])),
            total_target_words=output_data.get("total_target_words"),
            elapsed_seconds=round(elapsed, 2),
        )

        return AgentResult(
            success=True,
            output_data=output_data,
            tokens_used=self._total_tokens,
            cost_usd=self._total_cost,
            execution_time_seconds=round(elapsed, 2),
        )
