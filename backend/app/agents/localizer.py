"""Localizer agent -- cultural adaptation and market-specific localization.

This agent goes far beyond mechanical translation.  It rewrites content so that
currency references, market data, regulatory citations, cultural examples, and
idiomatic expressions feel *native* to the target market.

Supported target languages / markets:
    ja      -- Japanese (Japan real-estate market)
    en      -- English  (US / global real-estate market)
    id      -- Indonesian (Indonesia property market)
    zh-TW   -- Traditional Chinese (Taiwan real-estate market)
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.json_utils import extract_json
from app.config import settings

logger = structlog.get_logger(__name__)

# ── Supported languages & market profiles ────────────────────────────────────

SUPPORTED_LANGUAGES: set[str] = {"ja", "en", "id", "zh-TW"}

MARKET_PROFILES: dict[str, dict[str, str]] = {
    "ja": {
        "market_name": "Japan",
        "currency": "JPY (Japanese Yen, \u00a5)",
        "area_unit": "tsubo (\u5764) / square metres (m\u00b2)",
        "regulatory_body": "Ministry of Land, Infrastructure, Transport and Tourism (MLIT)",
        "typical_loan_term": "35 years fixed-rate",
        "tax_reference": "Fixed Asset Tax (\u56fa\u5b9a\u8cc7\u7523\u7a0e), Real Estate Acquisition Tax (\u4e0d\u52d5\u7523\u53d6\u5f97\u7a0e)",
        "cultural_notes": (
            "Emphasise safety, earthquake resistance, proximity to train stations. "
            "Use polite/formal register (\u3067\u3059\u30fb\u307e\u3059\u8abf). "
            "Seasons and school-year timing affect moving patterns."
        ),
    },
    "en": {
        "market_name": "United States / Global",
        "currency": "USD (US Dollar, $)",
        "area_unit": "square feet (sq ft)",
        "regulatory_body": "HUD / state-level real estate commissions",
        "typical_loan_term": "30-year fixed-rate mortgage",
        "tax_reference": "Property Tax, Capital Gains Tax, 1031 Exchange",
        "cultural_notes": (
            "Focus on ROI, neighbourhood safety scores, school district ratings. "
            "Use casual-professional tone. Reference MLS, Zillow, Redfin as known platforms."
        ),
    },
    "id": {
        "market_name": "Indonesia",
        "currency": "IDR (Indonesian Rupiah, Rp)",
        "area_unit": "square metres (m\u00b2)",
        "regulatory_body": "Ministry of Agrarian Affairs and Spatial Planning (ATR/BPN)",
        "typical_loan_term": "15\u201320 year KPR (Kredit Pemilikan Rumah)",
        "tax_reference": "BPHTB (Bea Perolehan Hak atas Tanah dan Bangunan), PBB (Pajak Bumi dan Bangunan)",
        "cultural_notes": (
            "Highlight flood-zone awareness, Sertifikat Hak Milik (SHM) vs HGB. "
            "Use Bahasa Indonesia with common English loan-words where natural. "
            "Reference major portals like Rumah123, OLX Properti."
        ),
    },
    "zh-TW": {
        "market_name": "Taiwan",
        "currency": "TWD (New Taiwan Dollar, NT$)",
        "area_unit": "ping (\u576a) / square metres (m\u00b2)",
        "regulatory_body": "Ministry of the Interior (MOI), Real Estate Transaction Act",
        "typical_loan_term": "20\u201330 year mortgage, often mixed-rate",
        "tax_reference": "Land Value Tax (\u5730\u50f9\u7a0e), House Tax (\u623f\u5c4b\u7a0e), Luxury Tax (\u5962\u4fb6\u7a0e on short-term sales)",
        "cultural_notes": (
            "Use Traditional Chinese characters. Emphasise floor numbering customs "
            "(avoid 4th floor), feng shui considerations, proximity to MRT stations. "
            "Reference 591\u623f\u5c4b\u4ea4\u6613, \u4fe1\u7fa9\u623f\u5c4b as known platforms."
        ),
    },
}


class LocalizerAgent(BaseAgent):
    """Localize and culturally adapt content for a specific target market.

    The agent receives an article in a source language and produces a fully
    localized version for the target market.  This includes -- but is not
    limited to -- language translation, currency conversion references,
    regulatory / tax rewrites, idiomatic expression adaptation, and
    cultural example substitution.
    """

    # ── BaseAgent abstract interface ─────────────────────────────────────

    @property
    def agent_name(self) -> str:
        return "localizer"

    @property
    def model_name(self) -> str:
        return settings.default_localizer_model

    @property
    def system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    # ── Execution ────────────────────────────────────────────────────────

    async def execute(self, context: AgentContext) -> AgentResult:
        """Localize *article_markdown* for *target_language* / *target_market*.

        Expected ``context.input_data`` keys:

        * ``article_markdown`` (str) -- the source Markdown article.
        * ``source_language`` (str) -- ISO code of the source, e.g. ``"ja"``.
        * ``target_language`` (str) -- ISO code of the target, e.g. ``"en"``.
        * ``target_market``  (str) -- free-text market descriptor; falls back
          to the target-language default if absent.

        Returns an :class:`AgentResult` whose ``output_data`` contains:

        * ``localized_markdown`` (str)
        * ``target_language`` (str)
        * ``localization_notes`` (list[str])
        * ``adapted_references`` (list[str])
        """
        self._reset_token_tracking()
        start = time.monotonic()
        log = self._log.bind(task_id=context.task_id)

        # --- unpack & validate from orchestrator cumulative_data ---------------
        data = context.input_data
        cal = data.get("calendar_entry", {})
        edit_step = data.get("edit", {})

        article_markdown: str = (
            edit_step.get("edited_markdown", "")
            or data.get("article_markdown", "")
        )
        source_language: str = cal.get("language", data.get("source_language", "ja"))
        target_language: str = data.get("target_language", "en")
        target_market: str = data.get("target_market", "")

        if not article_markdown.strip():
            return AgentResult(
                success=False,
                error_message="article_markdown is empty -- nothing to localize.",
            )

        if target_language not in SUPPORTED_LANGUAGES:
            return AgentResult(
                success=False,
                error_message=(
                    f"Unsupported target language '{target_language}'. "
                    f"Supported: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
                ),
            )

        market_profile = MARKET_PROFILES.get(target_language, {})
        market_description = target_market or market_profile.get("market_name", target_language)

        log.info(
            "localization_start",
            source_language=source_language,
            target_language=target_language,
            target_market=market_description,
            article_length=len(article_markdown),
        )

        # --- build user prompt ------------------------------------------------
        user_prompt = self._build_user_prompt(
            article_markdown=article_markdown,
            source_language=source_language,
            target_language=target_language,
            target_market=market_description,
            market_profile=market_profile,
        )

        # --- call LLM ---------------------------------------------------------
        response = await self._call_llm(
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=16384,
            temperature=0.4,
        )
        raw_text = self._text_from_response(response)

        # --- parse structured output ------------------------------------------
        parsed = self._parse_response(raw_text, target_language)

        elapsed = time.monotonic() - start
        log.info(
            "localization_complete",
            target_language=target_language,
            notes_count=len(parsed.get("localization_notes", [])),
            adapted_count=len(parsed.get("adapted_references", [])),
            tokens=self._total_tokens,
            elapsed_seconds=round(elapsed, 2),
        )

        return AgentResult(
            success=True,
            output_data=parsed,
            tokens_used=self._total_tokens,
            cost_usd=self._total_cost,
            execution_time_seconds=elapsed,
        )

    # ── Prompt construction ──────────────────────────────────────────────

    @staticmethod
    def _build_user_prompt(
        *,
        article_markdown: str,
        source_language: str,
        target_language: str,
        target_market: str,
        market_profile: dict[str, str],
    ) -> str:
        """Assemble the user-turn prompt for the localization call."""

        profile_block = ""
        if market_profile:
            profile_lines = "\n".join(
                f"  - {key}: {value}" for key, value in market_profile.items()
            )
            profile_block = (
                f"\n<market_profile>\n{profile_lines}\n</market_profile>\n"
            )

        return (
            f"Localize the following article from **{source_language}** to "
            f"**{target_language}** for the **{target_market}** market.\n"
            f"{profile_block}\n"
            "Adaptation requirements:\n"
            "1. Translate all text naturally -- do NOT produce a word-for-word translation.\n"
            "2. Replace currency amounts with the local currency equivalent "
            "(use approximate current rates; note the conversion in your localization notes).\n"
            "3. Substitute regulatory / tax references with the target market equivalents.\n"
            "4. Replace cultural examples, idioms, and analogies with ones "
            "that resonate in the target culture.\n"
            "5. Adapt any market-specific data (average prices, interest rates, "
            "popular platforms) to the target market.\n"
            "6. Preserve all Markdown formatting (headings, lists, links, images).\n"
            "7. Keep technical SEO elements (meta description placeholders, alt-text) "
            "in the target language.\n\n"
            "Return your output as a JSON object with exactly these keys:\n"
            "- \"localized_markdown\": the fully localized article in Markdown.\n"
            "- \"target_language\": the ISO language code you localized to.\n"
            "- \"localization_notes\": a JSON array of strings, each describing "
            "a noteworthy adaptation you made.\n"
            "- \"adapted_references\": a JSON array of strings, each describing "
            "a specific reference (regulation, platform, data point) you changed.\n\n"
            "Return ONLY the JSON object -- no extra commentary.\n\n"
            "<source_article>\n"
            f"{article_markdown}\n"
            "</source_article>"
        )

    # ── Response parsing ─────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw_text: str, target_language: str) -> dict[str, Any]:
        """Best-effort parse of the LLM JSON response."""
        try:
            data = extract_json(raw_text, allow_truncated=True)
            return {
                "localized_markdown": str(data.get("localized_markdown", raw_text)),
                "target_language": str(data.get("target_language", target_language)),
                "localization_notes": list(data.get("localization_notes", [])),
                "adapted_references": list(data.get("adapted_references", [])),
            }
        except (ValueError, json.JSONDecodeError):
            logger.warning(
                "localization_json_parse_failed",
                raw_length=len(raw_text),
            )
            return {
                "localized_markdown": raw_text,
                "target_language": target_language,
                "localization_notes": ["LLM response was not valid JSON; raw text used as-is."],
                "adapted_references": [],
            }


# ── System prompt (module-level constant) ────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a **professional localization specialist** with deep expertise in \
international real-estate markets.  Your work goes far beyond translation -- \
you perform full **cultural adaptation** so that the resulting article reads \
as though it were originally written by a native expert in the target market.

Core competencies:
- Fluent, publication-ready writing in Japanese, English, Indonesian, and \
Traditional Chinese.
- Deep knowledge of real-estate terminology, regulations, tax structures, \
and market dynamics in Japan, the United States, Indonesia, and Taiwan.
- Cultural sensitivity: you adapt idioms, analogies, humour, formality \
level, and examples to match the expectations of the target audience.
- SEO awareness: you preserve keyword intent while using naturally \
searched terms in the target language.

Strict rules:
1. NEVER produce translationese -- every sentence must sound natural to a \
native speaker.
2. Currency amounts MUST be converted to the target market's currency using \
approximate current exchange rates.  Note the conversion in your \
localization notes.
3. Regulatory and tax references MUST be replaced with the correct \
equivalents for the target jurisdiction.
4. Cultural examples (e.g., popular platforms, neighbourhood descriptions, \
seasonal references) MUST be substituted with locally relevant ones.
5. Markdown structure (headings, bullet lists, links, image references) \
MUST be preserved exactly.
6. You MUST return valid JSON matching the schema described in the user \
prompt -- no extra text outside the JSON object.
"""
