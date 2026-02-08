"""Researcher agent -- gathers market data, statistics, and competitor insights.

This agent sits at the beginning of the content pipeline.  It uses the Tavily
web-search API to collect recent, high-quality sources and then asks the LLM to
synthesise them into a structured research report that downstream agents
(Planner, Writer, ...) can consume.

When Tavily is not configured or all searches fail, the agent falls back to
the LLM's own knowledge to produce the research report.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx
import structlog

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.json_utils import extract_json
from app.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_SOURCES = 5
_MIN_STATISTICS = 3
# Lower thresholds when no web search data is available
_MIN_SOURCES_LLM_ONLY = 0
_MIN_STATISTICS_LLM_ONLY = 1

RESEARCHER_SYSTEM_PROMPT = """\
You are an expert real-estate and PropTech research analyst working for \
knock knock AI, a content-marketing automation platform focused on the \
Japanese real-estate market.

Your responsibilities:
- Analyse raw web-search results (if provided) and extract the most relevant \
  facts, statistics, market trends, and competitor moves.
- If no web-search results are provided, use your own knowledge to produce \
  a comprehensive research report.
- Produce a well-structured research report in **Markdown** that a content \
  planner and writer can use directly.
- Always cite your sources with URLs when available.
- Separate hard data (numbers, percentages, dates) from qualitative \
  observations.
- Highlight information that is especially useful for SEO-driven blog \
  articles targeting property buyers, sellers, investors, and PropTech \
  professionals in Japan.
- When information is uncertain or conflicting, note the discrepancy rather \
  than guessing.

You MUST respond with ONLY a JSON object (no markdown fences, no preamble, \
no commentary before or after):
{
  "research_report": "<Markdown string>",
  "key_statistics": [
    {"stat": "<description>", "source": "<url or 'LLM knowledge'>", "date": "<YYYY-MM-DD or approximate>"}
  ],
  "competitor_insights": "<Markdown string>",
  "market_data": "<Markdown string>",
  "sources": ["<url1>", "<url2>", ...]
}
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
    """Execute a single Tavily web-search request."""
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
    """Collects market data, statistics, competitor info, and latest news."""

    @property
    def agent_name(self) -> str:
        return "researcher"

    @property
    def model_name(self) -> str:
        return settings.default_researcher_model

    @property
    def system_prompt(self) -> str:
        return RESEARCHER_SYSTEM_PROMPT

    def _build_search_queries(
        self,
        article_theme: str,
        target_keywords: list[str],
        target_market: str,
    ) -> list[str]:
        keyword_str = ", ".join(target_keywords) if target_keywords else article_theme

        queries = [
            f"{article_theme} {target_market} latest trends",
            f"{keyword_str} statistics data {target_market}",
            f"{article_theme} competitors market share {target_market}",
            f"{article_theme} {target_market} news 2024 2025",
        ]

        if target_keywords:
            queries.append(f"{' '.join(target_keywords[:3])} {target_market} insights")

        return queries

    @staticmethod
    def _format_search_results(all_results: list[dict[str, Any]]) -> str:
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

    @staticmethod
    def _check_data_sufficiency(
        output_data: dict[str, Any],
        *,
        llm_only: bool = False,
    ) -> tuple[bool, str]:
        sources = output_data.get("sources", [])
        statistics = output_data.get("key_statistics", [])

        min_src = _MIN_SOURCES_LLM_ONLY if llm_only else _MIN_SOURCES
        min_stat = _MIN_STATISTICS_LLM_ONLY if llm_only else _MIN_STATISTICS

        issues: list[str] = []
        if len(sources) < min_src:
            issues.append(
                f"Insufficient sources: found {len(sources)}, need >= {min_src}"
            )
        if len(statistics) < min_stat:
            issues.append(
                f"Insufficient statistics: found {len(statistics)}, need >= {min_stat}"
            )

        if issues:
            return False, "; ".join(issues)
        return True, ""

    async def execute(self, context: AgentContext) -> AgentResult:
        self._reset_token_tracking()
        start = time.monotonic()

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

        # ---- 1. Web search via Tavily (optional) --------------------------------
        llm_only = False
        all_search_results: list[dict[str, Any]] = []

        if settings.tavily_api_key:
            queries = self._build_search_queries(article_theme, target_keywords, target_market)
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
                except (httpx.RequestError, Exception) as exc:
                    self._log.warning("tavily_request_error", query=query, error=str(exc))
        else:
            self._log.info("tavily_not_configured", msg="Falling back to LLM knowledge")

        if not all_search_results:
            llm_only = True
            self._log.info("using_llm_knowledge_only")

        # ---- 2. LLM synthesis ----------------------------------------------------
        if llm_only:
            user_prompt = (
                f"Article theme: {article_theme}\n"
                f"Target keywords: {', '.join(target_keywords)}\n"
                f"Target market: {target_market}\n\n"
                f"No web search results are available. Use your own knowledge to "
                f"produce a comprehensive research report about this topic. "
                f"Include relevant statistics, market trends, and competitor insights "
                f"based on your training data. For sources, use 'LLM knowledge' where "
                f"you cannot provide a specific URL.\n\n"
                f"Respond with ONLY a JSON object (no markdown fences)."
            )
        else:
            formatted_results = self._format_search_results(all_search_results)
            user_prompt = (
                f"Article theme: {article_theme}\n"
                f"Target keywords: {', '.join(target_keywords)}\n"
                f"Target market: {target_market}\n\n"
                f"Below are the raw web-search results. Analyse them and produce "
                f"the JSON output described in your system instructions.\n\n"
                f"Respond with ONLY a JSON object (no markdown fences).\n\n"
                f"{formatted_results}"
            )

        response = await self._call_llm(
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=16384,
            temperature=0.3,
        )

        raw_text = self._text_from_response(response)
        truncated = response.stop_reason == "max_tokens"

        # ---- 3. Parse the LLM JSON output ----------------------------------------
        try:
            output_data = extract_json(raw_text, allow_truncated=truncated)
        except (ValueError, json.JSONDecodeError) as parse_err:
            elapsed = time.monotonic() - start
            self._log.error(
                "json_parse_failed",
                error=str(parse_err),
                raw_text_preview=raw_text[:500],
            )
            return AgentResult(
                success=False,
                output_data={"raw_response": raw_text[:2000]},
                error_message=f"Failed to parse LLM output as JSON: {parse_err}",
                tokens_used=self._total_tokens,
                cost_usd=self._total_cost,
                execution_time_seconds=round(time.monotonic() - start, 2),
            )

        # ---- 4. Quality gate: data sufficiency -----------------------------------
        passed, reason = self._check_data_sufficiency(output_data, llm_only=llm_only)

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
            llm_only=llm_only,
            elapsed_seconds=round(elapsed, 2),
        )

        return AgentResult(
            success=True,
            output_data=output_data,
            tokens_used=self._total_tokens,
            cost_usd=self._total_cost,
            execution_time_seconds=round(elapsed, 2),
        )
