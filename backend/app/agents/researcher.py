"""Researcher agent -- gathers market data, statistics, and competitor insights.

This agent sits at the beginning of the content pipeline.  It uses the Tavily
web-search API to collect recent, high-quality sources and then asks the LLM to
synthesise them into a structured research report that downstream agents
(Planner, Writer, ...) can consume.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import structlog

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_SOURCES = 5
_MIN_STATISTICS = 3

RESEARCHER_SYSTEM_PROMPT = """\
You are an expert real-estate and PropTech research analyst working for \
knock knock AI, a content-marketing automation platform focused on the \
Japanese real-estate market.

Your responsibilities:
- Analyse raw web-search results and extract the most relevant facts, \
  statistics, market trends, and competitor moves.
- Produce a well-structured research report in **Markdown** that a content \
  planner and writer can use directly.
- Always cite your sources with URLs.
- Separate hard data (numbers, percentages, dates) from qualitative \
  observations.
- Highlight information that is especially useful for SEO-driven blog \
  articles targeting property buyers, sellers, investors, and PropTech \
  professionals in Japan.
- When information is uncertain or conflicting, note the discrepancy rather \
  than guessing.

Output format (strict JSON):
{
  "research_report": "<Markdown string>",
  "key_statistics": [
    {"stat": "<description>", "source": "<url>", "date": "<YYYY-MM-DD or approximate>"}
  ],
  "competitor_insights": "<Markdown string>",
  "market_data": "<Markdown string>",
  "sources": ["<url1>", "<url2>", ...]
}

Return ONLY valid JSON -- no commentary outside the JSON block.
"""

# ---------------------------------------------------------------------------
# Tavily search helper
# ---------------------------------------------------------------------------

_TAVILY_SEARCH_URL = "https://api.tavily.com/search"


async def _tavily_search(
    query: str,
    *,
    max_results: int = 10,
    search_depth: str = "advanced",
    include_raw_content: bool = False,
) -> list[dict[str, Any]]:
    """Execute a single Tavily web-search request.

    Returns a list of result dicts, each containing at minimum the keys
    ``title``, ``url``, ``content``, and ``score``.
    """
    log = logger.bind(component="tavily_search")
    payload: dict[str, Any] = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_raw_content": include_raw_content,
    }

    log.info("tavily_request", query=query, max_results=max_results)
    start = time.monotonic()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_TAVILY_SEARCH_URL, json=payload)
        resp.raise_for_status()

    elapsed = time.monotonic() - start
    data = resp.json()
    results: list[dict[str, Any]] = data.get("results", [])
    log.info(
        "tavily_response",
        result_count=len(results),
        elapsed_seconds=round(elapsed, 2),
    )
    return results


# ---------------------------------------------------------------------------
# Researcher agent
# ---------------------------------------------------------------------------


class ResearcherAgent(BaseAgent):
    """Collects market data, statistics, competitor info, and latest news.

    The agent performs several Tavily searches derived from the article theme
    and target keywords, then asks the LLM to synthesise the raw results into
    a structured JSON report.
    """

    # --- BaseAgent interface --------------------------------------------------

    @property
    def agent_name(self) -> str:
        return "researcher"

    @property
    def model_name(self) -> str:
        return settings.default_researcher_model

    @property
    def system_prompt(self) -> str:
        return RESEARCHER_SYSTEM_PROMPT

    # --- internal helpers -----------------------------------------------------

    def _build_search_queries(
        self,
        article_theme: str,
        target_keywords: list[str],
        target_market: str,
    ) -> list[str]:
        """Derive a set of search queries from the pipeline inputs.

        We generate several complementary queries so the final report covers
        general market data, statistics, competitor activity, and recent news.
        """
        keyword_str = ", ".join(target_keywords) if target_keywords else article_theme

        queries = [
            # Broad thematic search
            f"{article_theme} {target_market} latest trends",
            # Statistics / data-focused
            f"{keyword_str} statistics data {target_market}",
            # Competitor / industry players
            f"{article_theme} competitors market share {target_market}",
            # Recent news
            f"{article_theme} {target_market} news 2024 2025",
        ]

        # Add a keyword-specific query if keywords differ from the theme
        if target_keywords:
            queries.append(f"{' '.join(target_keywords[:3])} {target_market} insights")

        return queries

    @staticmethod
    def _format_search_results(all_results: list[dict[str, Any]]) -> str:
        """Collapse Tavily results into a single text block for the LLM."""
        parts: list[str] = []
        seen_urls: set[str] = set()

        for idx, result in enumerate(all_results, 1):
            url = result.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = result.get("title", "No title")
            content = result.get("content", "")
            score = result.get("score", 0.0)
            parts.append(
                f"--- Result {idx} (relevance {score:.2f}) ---\n"
                f"Title: {title}\n"
                f"URL: {url}\n"
                f"Content:\n{content}\n"
            )

        return "\n".join(parts)

    # --- quality gate ---------------------------------------------------------

    @staticmethod
    def _check_data_sufficiency(output_data: dict[str, Any]) -> tuple[bool, str]:
        """Verify that the research output meets minimum thresholds.

        Requirements:
        * At least ``_MIN_SOURCES`` unique source URLs.
        * At least ``_MIN_STATISTICS`` entries in ``key_statistics``.

        Returns:
            ``(passed, reason)`` where *reason* is an empty string on success.
        """
        sources = output_data.get("sources", [])
        statistics = output_data.get("key_statistics", [])

        issues: list[str] = []
        if len(sources) < _MIN_SOURCES:
            issues.append(
                f"Insufficient sources: found {len(sources)}, need >= {_MIN_SOURCES}"
            )
        if len(statistics) < _MIN_STATISTICS:
            issues.append(
                f"Insufficient statistics: found {len(statistics)}, need >= {_MIN_STATISTICS}"
            )

        if issues:
            return False, "; ".join(issues)
        return True, ""

    # --- execute --------------------------------------------------------------

    async def execute(self, context: AgentContext) -> AgentResult:
        """Run the full research cycle.

        Expected keys in ``context.input_data``:

        * ``article_theme`` (str) -- The central topic of the article.
        * ``target_keywords`` (list[str]) -- SEO keywords to research.
        * ``target_market`` (str) -- Geographic / demographic market scope.
        """
        self._reset_token_tracking()
        start = time.monotonic()

        # The orchestrator passes cumulative_data which nests the calendar
        # entry under the "calendar_entry" key.  Fall back to top-level keys
        # for standalone usage.
        cal = context.input_data.get("calendar_entry", {})
        article_theme: str = (
            cal.get("topic", "")
            or context.input_data.get("article_theme", "")
        )
        target_keywords: list[str] = (
            cal.get("target_keywords")
            or context.input_data.get("target_keywords", [])
        )
        target_market: str = (
            cal.get("target_market", "")
            or context.input_data.get("target_market", "Japan real estate")
        )

        self._log.info(
            "researcher_execute_start",
            article_theme=article_theme,
            target_keywords=target_keywords,
            target_market=target_market,
        )

        # ---- 1. Web search via Tavily ----------------------------------------
        queries = self._build_search_queries(article_theme, target_keywords, target_market)
        all_search_results: list[dict[str, Any]] = []

        for query in queries:
            try:
                results = await _tavily_search(query, max_results=8)
                all_search_results.extend(results)
            except httpx.HTTPStatusError as exc:
                self._log.warning(
                    "tavily_search_failed",
                    query=query,
                    status_code=exc.response.status_code,
                    detail=exc.response.text[:500],
                )
            except httpx.RequestError as exc:
                self._log.warning("tavily_request_error", query=query, error=str(exc))

        if not all_search_results:
            elapsed = time.monotonic() - start
            self._log.error("no_search_results")
            return AgentResult(
                success=False,
                error_message="All Tavily searches failed -- no raw data to synthesise.",
                execution_time_seconds=round(elapsed, 2),
            )

        formatted_results = self._format_search_results(all_search_results)

        # ---- 2. LLM synthesis ------------------------------------------------
        user_prompt = (
            f"Article theme: {article_theme}\n"
            f"Target keywords: {', '.join(target_keywords)}\n"
            f"Target market: {target_market}\n\n"
            f"Below are the raw web-search results.  Analyse them and produce "
            f"the JSON output described in your system instructions.\n\n"
            f"{formatted_results}"
        )

        response = await self._call_llm(
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=4096,
            temperature=0.3,
        )

        raw_text = self._text_from_response(response)

        # ---- 3. Parse the LLM JSON output ------------------------------------
        try:
            output_data: dict[str, Any] = json.loads(raw_text)
        except json.JSONDecodeError:
            # Attempt to extract a JSON block from markdown fences
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

        # ---- 4. Quality gate: data sufficiency -------------------------------
        passed, reason = self._check_data_sufficiency(output_data)

        elapsed = time.monotonic() - start

        if not passed:
            self._log.warning("data_sufficiency_failed", reason=reason)
            return AgentResult(
                success=False,
                output_data=output_data,
                error_message=f"Quality gate failed: {reason}",
                tokens_used=self._total_tokens,
                cost_usd=self._total_cost,
                execution_time_seconds=round(elapsed, 2),
            )

        self._log.info(
            "researcher_execute_complete",
            source_count=len(output_data.get("sources", [])),
            stat_count=len(output_data.get("key_statistics", [])),
            elapsed_seconds=round(elapsed, 2),
        )

        return AgentResult(
            success=True,
            output_data=output_data,
            tokens_used=self._total_tokens,
            cost_usd=self._total_cost,
            execution_time_seconds=round(elapsed, 2),
        )
