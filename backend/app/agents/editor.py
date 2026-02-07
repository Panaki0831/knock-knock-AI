"""Editor Agent -- quality-assurance gate for the knock knock AI pipeline.

The Editor reviews draft articles produced by the Writer and assigns scores
across five quality dimensions.  If all scores meet the minimum threshold the
article is approved; otherwise the Editor produces detailed revision
instructions that are fed back to the Writer for another iteration.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import structlog

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Quality gate thresholds
# ---------------------------------------------------------------------------

SCORE_MIN_INDIVIDUAL = 70  # Every score must be >= this value
SCORE_MIN_AVERAGE = 75     # The arithmetic mean of all scores must be >= this

# ---------------------------------------------------------------------------
# Score dimension definitions (used in the prompt)
# ---------------------------------------------------------------------------

_SCORE_DIMENSIONS = """\
You must evaluate the article across EXACTLY these five dimensions.  For each
dimension, assign an integer score from 0 to 100 and provide a brief
justification (1-3 sentences).

### 1. readability_score (0-100)
Measures how easy and enjoyable the article is to read.
- Sentence variety: are consecutive sentences structurally diverse?
- Paragraph length: are paragraphs kept to 3-5 sentences?
- Clarity: can a non-expert understand the main points?
- Flow: do transitions between paragraphs feel natural?

### 2. seo_score (0-100)
Measures how well the article is optimised for search engines.
- Keyword placement: do target keywords appear in H1, H2, first paragraph,
  and naturally throughout?
- Meta description: is there content suitable for a ~155-character meta
  description?
- Heading structure: is there a clear H1 > H2 > H3 hierarchy?
- Internal linking opportunities: are there natural anchor points?
- Content length: is the article substantive enough for the target keywords?

### 3. ai_detection_score (0-100)
Measures how "human" the writing feels -- higher is MORE human.
- Pattern diversity: does the text avoid repetitive sentence openers?
- Vocabulary range: is there natural variation in word choice?
- Idiomatic expressions: does the writing use natural idioms and
  colloquialisms appropriate for the target language?
- Perspective and opinion: does the article contain genuine-sounding
  opinions and experience-based insights?
- Burstiness: does sentence length vary naturally (short-long-medium pattern)?

### 4. factual_accuracy_score (0-100)
Measures whether claims are grounded in the provided research.
- Source backing: can each major claim be traced to the research report?
- No fabrication: are there any statistics, quotes, or facts that do NOT
  appear in the research?
- Hedging: are uncertain claims appropriately qualified?
- Recency: does the article avoid presenting dated information as current?

### 5. brand_consistency_score (0-100)
Measures alignment with knock knock AI's brand voice.
- Tone: warm, confident, conversational -- not robotic or stiff?
- Perspective: uses "we" for knock knock AI and "you" for the reader?
- Actionability: does each section offer concrete takeaways?
- Prohibited phrases: free of filler phrases and passive-voice overuse?
"""

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_EVALUATION_PROMPT = """\
You are reviewing the following article draft for the knock knock AI content
marketing platform.  Your job is to evaluate quality and provide actionable
feedback.

## Article Draft
{article_markdown}

## Research Report (ground truth for factual accuracy)
{research_report}

## Target Keywords
{target_keywords}

## SEO Plan
{seo_plan}

## Scoring Instructions
{score_dimensions}

## Output Format
You MUST respond with valid JSON and NOTHING else -- no markdown fences, no
commentary before or after the JSON.  Use this exact structure:

{{
  "scores": {{
    "readability_score": <int>,
    "seo_score": <int>,
    "ai_detection_score": <int>,
    "factual_accuracy_score": <int>,
    "brand_consistency_score": <int>
  }},
  "justifications": {{
    "readability_score": "<1-3 sentence justification>",
    "seo_score": "<1-3 sentence justification>",
    "ai_detection_score": "<1-3 sentence justification>",
    "factual_accuracy_score": "<1-3 sentence justification>",
    "brand_consistency_score": "<1-3 sentence justification>"
  }},
  "overall_feedback": "<2-4 sentence summary of the article's strengths and weaknesses>",
  "line_edits": [
    {{
      "location": "<section heading or line excerpt>",
      "issue": "<what is wrong>",
      "suggestion": "<how to fix it>"
    }}
  ]
}}
"""

_REVISION_INSTRUCTIONS_PROMPT = """\
Based on the quality evaluation below, write detailed, actionable revision
instructions that a Writer agent can follow to improve the article.  The
instructions should be specific enough that the Writer knows EXACTLY what to
change without needing to re-read the evaluation.

## Quality Scores
{scores_json}

## Justifications
{justifications_json}

## Line-Level Edits
{line_edits_json}

## Overall Feedback
{overall_feedback}

## Failing Dimensions
{failing_dimensions}

## Instructions Format
Write the revision instructions as a numbered list.  Group related items
under the dimension they address.  Be concrete: quote the problematic text
and provide a rewritten example where possible.

Output ONLY the revision instructions -- no preamble or closing commentary.
"""

_COPY_EDIT_PROMPT = """\
You are a meticulous copy-editor.  Apply light edits to the article below to
fix:
- Grammar and spelling errors
- Awkward phrasing
- Overly long sentences (split them)
- Missing or inconsistent Markdown formatting

Do NOT change the article's structure, voice, or meaning.  Preserve all
headings, lists, and emphasis.  Output ONLY the edited Markdown.

## Article
{article_markdown}
"""


class EditorAgent(BaseAgent):
    """Reviews and scores articles against five quality dimensions.

    The Editor acts as a quality gate: if the article meets all score
    thresholds it is approved with light copy-edits applied; otherwise it
    returns detailed revision instructions for the Writer to address.
    """

    # ------------------------------------------------------------------ #
    # BaseAgent abstract interface                                        #
    # ------------------------------------------------------------------ #

    @property
    def agent_name(self) -> str:
        return "editor"

    @property
    def model_name(self) -> str:
        return settings.default_editor_model

    @property
    def system_prompt(self) -> str:
        return (
            "You are the senior editor and quality-assurance specialist for "
            "**knock knock AI**, an AI-driven content-marketing platform.  "
            "Your mission is to ensure every published article meets the highest "
            "standards of readability, SEO effectiveness, factual accuracy, "
            "brand consistency, and human authenticity.\n\n"
            "You are rigorous but fair.  You cite specific examples when giving "
            "feedback and always suggest concrete improvements rather than vague "
            "criticism.  You respond ONLY in the exact JSON or Markdown format "
            "requested -- never add unsolicited commentary."
        )

    # ------------------------------------------------------------------ #
    # Main execution                                                      #
    # ------------------------------------------------------------------ #

    async def execute(self, context: AgentContext) -> AgentResult:
        """Evaluate an article and decide whether it passes the quality gate.

        Expected ``context.input_data`` keys:

        * **article_markdown** (``str``): The draft article to review.
        * **research_report** (``str``): The original research used by the
          Writer, serving as ground truth for factual-accuracy scoring.
        * **target_keywords** (``list[str]``): Primary and secondary keywords
          the article should rank for.
        * **seo_plan** (``str``, optional): SEO strategy notes (heading
          targets, internal link anchors, etc.).

        Returns an :class:`AgentResult` whose ``output_data`` contains:

        * **edited_markdown** (``str``): Copy-edited article (only when
          *passed* is ``True``; otherwise the original is returned).
        * **quality_scores** (``dict``): Mapping of dimension name to integer
          score.
        * **passed** (``bool``): Whether the article passed the quality gate.
        * **feedback** (``str``): Human-readable summary of strengths and
          weaknesses.
        * **revision_instructions** (``str``): Detailed instructions for the
          Writer -- present only when ``passed`` is ``False``.
        """
        self._reset_token_tracking()
        start_time = time.monotonic()

        self._log.info("editor_execute_start", task_id=context.task_id)

        # ----- extract inputs ------------------------------------------------
        article_markdown: str = context.input_data.get("article_markdown", "")
        research_report: str = context.input_data.get("research_report", "")
        target_keywords: list[str] = context.input_data.get("target_keywords", [])
        seo_plan: str = context.input_data.get("seo_plan", "")

        if not article_markdown:
            return AgentResult(
                success=False,
                error_message=(
                    "No article provided in context.input_data['article_markdown']."
                ),
                execution_time_seconds=time.monotonic() - start_time,
            )

        # ----- Step 1: Evaluate quality --------------------------------------
        evaluation = await self._evaluate_article(
            article_markdown=article_markdown,
            research_report=research_report,
            target_keywords=target_keywords,
            seo_plan=seo_plan,
        )

        if evaluation is None:
            return AgentResult(
                success=False,
                error_message="Failed to parse quality evaluation from LLM response.",
                tokens_used=self._total_tokens,
                cost_usd=self._total_cost,
                execution_time_seconds=time.monotonic() - start_time,
            )

        scores: dict[str, int] = evaluation["scores"]
        justifications: dict[str, str] = evaluation["justifications"]
        overall_feedback: str = evaluation.get("overall_feedback", "")
        line_edits: list[dict[str, str]] = evaluation.get("line_edits", [])

        # ----- Step 2: Check quality gate ------------------------------------
        passed, failing_dimensions = self._check_quality_gate(scores)

        self._log.info(
            "editor_quality_gate",
            scores=scores,
            passed=passed,
            failing_dimensions=failing_dimensions,
        )

        # ----- Step 3a: If failed, generate revision instructions ------------
        revision_instructions: str | None = None
        edited_markdown = article_markdown  # default: return original

        if not passed:
            revision_instructions = await self._generate_revision_instructions(
                scores=scores,
                justifications=justifications,
                line_edits=line_edits,
                overall_feedback=overall_feedback,
                failing_dimensions=failing_dimensions,
            )

            self._log.info(
                "editor_revision_instructions_generated",
                failing_count=len(failing_dimensions),
            )

        # ----- Step 3b: If passed, apply light copy-edits --------------------
        if passed:
            edited_markdown = await self._copy_edit(article_markdown)
            self._log.info("editor_copy_edit_complete")

        # ----- Assemble result -----------------------------------------------
        elapsed = time.monotonic() - start_time

        output_data: dict[str, Any] = {
            "edited_markdown": edited_markdown,
            "quality_scores": scores,
            "passed": passed,
            "feedback": overall_feedback,
        }
        if revision_instructions is not None:
            output_data["revision_instructions"] = revision_instructions

        self._log.info(
            "editor_execute_complete",
            passed=passed,
            tokens_used=self._total_tokens,
            cost_usd=round(self._total_cost, 6),
            elapsed_seconds=round(elapsed, 2),
        )

        return AgentResult(
            success=True,
            output_data=output_data,
            tokens_used=self._total_tokens,
            cost_usd=self._total_cost,
            execution_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------ #
    # Private helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _evaluate_article(
        self,
        *,
        article_markdown: str,
        research_report: str,
        target_keywords: list[str],
        seo_plan: str,
    ) -> dict[str, Any] | None:
        """Ask the LLM to score the article across five dimensions.

        Returns the parsed JSON evaluation dict, or ``None`` if the response
        could not be parsed.
        """
        keywords_str = ", ".join(target_keywords) if target_keywords else "(none provided)"
        seo_plan_str = seo_plan if seo_plan else "(no SEO plan provided)"

        user_message = _EVALUATION_PROMPT.format(
            article_markdown=article_markdown,
            research_report=research_report,
            target_keywords=keywords_str,
            seo_plan=seo_plan_str,
            score_dimensions=_SCORE_DIMENSIONS,
        )

        response = await self._call_llm(
            [{"role": "user", "content": user_message}],
            max_tokens=4096,
            temperature=0.3,  # low temperature for consistent scoring
        )
        raw_text = self._text_from_response(response)

        return self._parse_evaluation_json(raw_text)

    async def _generate_revision_instructions(
        self,
        *,
        scores: dict[str, int],
        justifications: dict[str, str],
        line_edits: list[dict[str, str]],
        overall_feedback: str,
        failing_dimensions: list[str],
    ) -> str:
        """Produce detailed, actionable revision instructions for the Writer."""
        user_message = _REVISION_INSTRUCTIONS_PROMPT.format(
            scores_json=json.dumps(scores, indent=2),
            justifications_json=json.dumps(justifications, indent=2, ensure_ascii=False),
            line_edits_json=json.dumps(line_edits, indent=2, ensure_ascii=False),
            overall_feedback=overall_feedback,
            failing_dimensions=", ".join(failing_dimensions),
        )

        response = await self._call_llm(
            [{"role": "user", "content": user_message}],
            max_tokens=4096,
            temperature=0.4,
        )
        return self._text_from_response(response)

    async def _copy_edit(self, article_markdown: str) -> str:
        """Apply light copy-edits to an approved article."""
        user_message = _COPY_EDIT_PROMPT.format(article_markdown=article_markdown)

        response = await self._call_llm(
            [{"role": "user", "content": user_message}],
            max_tokens=8192,
            temperature=0.25,  # very low -- preserve original voice
        )
        return self._text_from_response(response)

    # ------------------------------------------------------------------ #
    # Quality gate logic                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _check_quality_gate(
        scores: dict[str, int],
    ) -> tuple[bool, list[str]]:
        """Determine whether the article passes the quality gate.

        Rules:
        1. Every individual score must be >= ``SCORE_MIN_INDIVIDUAL`` (70).
        2. The arithmetic mean of all scores must be >= ``SCORE_MIN_AVERAGE``
           (75).

        Returns:
            A tuple of ``(passed, failing_dimensions)`` where
            ``failing_dimensions`` lists dimension names that contributed to
            the failure.
        """
        failing: list[str] = []

        for dimension, score in scores.items():
            if score < SCORE_MIN_INDIVIDUAL:
                failing.append(dimension)

        all_scores = list(scores.values())
        average = sum(all_scores) / len(all_scores) if all_scores else 0
        average_ok = average >= SCORE_MIN_AVERAGE

        if not average_ok and not failing:
            # Average is too low but no single score is below the individual
            # threshold -- flag all dimensions as contributing so the Writer
            # knows to improve broadly.
            failing = list(scores.keys())

        passed = len(failing) == 0 and average_ok
        return passed, failing

    # ------------------------------------------------------------------ #
    # JSON parsing                                                        #
    # ------------------------------------------------------------------ #

    def _parse_evaluation_json(self, raw_text: str) -> dict[str, Any] | None:
        """Robustly extract the evaluation JSON from the LLM response.

        Handles cases where the LLM wraps the JSON in markdown fences or
        adds preamble/postamble text.
        """
        # Try direct parse first
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code fences
        fence_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw_text, re.DOTALL
        )
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding the first { ... } block
        brace_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        self._log.error(
            "editor_json_parse_failed",
            raw_text_length=len(raw_text),
            raw_text_preview=raw_text[:500],
        )
        return None
