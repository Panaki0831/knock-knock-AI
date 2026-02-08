"""Publisher agent -- format conversion and multi-platform publishing.

This agent converts a finished Markdown article into the platform-specific
format required by each publishing target, generates companion SNS share
texts, and (when API credentials are available) posts directly to the
platform.

Supported platforms:
    note        -- note.com (Japanese blogging platform)
    medium      -- Medium.com
    wordpress   -- Self-hosted WordPress via REST API
    zenn        -- Zenn.dev  (Japanese developer blogging)
    hatena      -- Hatena Blog (Japanese blogging platform)
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import structlog

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.json_utils import extract_json
from app.config import settings

logger = structlog.get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

SUPPORTED_PLATFORMS: set[str] = {"note", "medium", "wordpress", "zenn", "hatena"}

# Maximum character limits for SNS share texts.
_TWITTER_CHAR_LIMIT = 280
_LINKEDIN_CHAR_LIMIT = 3000
_EMAIL_SUMMARY_LIMIT = 500


class PublisherAgent(BaseAgent):
    """Convert Markdown content for a target platform and optionally publish.

    The agent performs three tasks in a single execution:

    1. **Format conversion** -- rewrite the Markdown into the target platform's
       native format (HTML, API-specific Markdown dialect, front-matter, etc.).
    2. **SNS text generation** -- produce ready-to-post share texts for
       Twitter/X and LinkedIn.
    3. **Email summary** -- generate a concise newsletter-friendly summary.

    If valid API credentials are configured the agent will also attempt to
    publish the article and return the ``published_url``.
    """

    # ── BaseAgent abstract interface ─────────────────────────────────────

    @property
    def agent_name(self) -> str:
        return "publisher"

    @property
    def model_name(self) -> str:
        return settings.default_publisher_model

    @property
    def system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    # ── Execution ────────────────────────────────────────────────────────

    async def execute(self, context: AgentContext) -> AgentResult:
        """Format, generate share texts, and optionally publish.

        Expected ``context.input_data`` keys:

        * ``article_markdown`` (str) -- the final Markdown article.
        * ``target_platform`` (str) -- one of the supported platform slugs.
        * ``article_metadata`` (dict) -- at minimum ``{"title": "...", "tags": [...]}``.

        Returns an :class:`AgentResult` whose ``output_data`` contains:

        * ``published_url`` (str | None)
        * ``platform`` (str)
        * ``sns_posts`` (dict) -- ``{"twitter": "...", "linkedin": "..."}``
        * ``email_summary`` (str)
        * ``formatted_content`` (str)
        """
        self._reset_token_tracking()
        start = time.monotonic()
        log = self._log.bind(task_id=context.task_id)

        # --- unpack & validate from orchestrator cumulative_data ---------------
        data = context.input_data
        cal = data.get("calendar_entry", {})
        edit_step = data.get("edit", {})
        localize_step = data.get("localize", {})
        plan_step = data.get("plan", {})

        article_markdown: str = (
            localize_step.get("localized_markdown", "")
            or edit_step.get("edited_markdown", "")
            or data.get("article_markdown", "")
        )
        target_platform: str = (
            cal.get("target_platforms", [""])[0] if cal.get("target_platforms") else
            cal.get("target_platform", data.get("target_platform", ""))
        ).lower()
        article_metadata: dict[str, Any] = data.get("article_metadata", {
            "title": plan_step.get("outline", {}).get("h1", cal.get("topic", "Untitled")),
            "tags": cal.get("target_keywords", []),
        })

        if not article_markdown.strip():
            return AgentResult(
                success=False,
                error_message="article_markdown is empty -- nothing to publish.",
            )

        if target_platform not in SUPPORTED_PLATFORMS:
            return AgentResult(
                success=False,
                error_message=(
                    f"Unsupported platform '{target_platform}'. "
                    f"Supported: {', '.join(sorted(SUPPORTED_PLATFORMS))}"
                ),
            )

        title: str = article_metadata.get("title", "Untitled")
        tags: list[str] = article_metadata.get("tags", [])

        log.info(
            "publish_start",
            platform=target_platform,
            title=title,
            article_length=len(article_markdown),
        )

        # --- Step 1: format conversion + SNS + email via a single LLM call ---
        user_prompt = self._build_user_prompt(
            article_markdown=article_markdown,
            target_platform=target_platform,
            title=title,
            tags=tags,
            article_metadata=article_metadata,
        )

        response = await self._call_llm(
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=16384,
            temperature=0.3,
        )
        raw_text = self._text_from_response(response)
        parsed = self._parse_response(raw_text, target_platform)

        formatted_content: str = parsed.get("formatted_content", article_markdown)
        sns_posts: dict[str, str] = parsed.get("sns_posts", {})
        email_summary: str = parsed.get("email_summary", "")

        # --- Step 2: attempt API publish if credentials exist -----------------
        published_url: str | None = None
        try:
            published_url = await self._publish_to_platform(
                platform=target_platform,
                formatted_content=formatted_content,
                title=title,
                tags=tags,
                article_metadata=article_metadata,
            )
        except Exception as exc:
            log.warning(
                "publish_api_call_failed",
                platform=target_platform,
                error=str(exc),
            )
            # Non-fatal: we still return the formatted content.

        elapsed = time.monotonic() - start
        log.info(
            "publish_complete",
            platform=target_platform,
            published_url=published_url,
            tokens=self._total_tokens,
            elapsed_seconds=round(elapsed, 2),
        )

        return AgentResult(
            success=True,
            output_data={
                "published_url": published_url,
                "platform": target_platform,
                "sns_posts": sns_posts,
                "email_summary": email_summary,
                "formatted_content": formatted_content,
            },
            tokens_used=self._total_tokens,
            cost_usd=self._total_cost,
            execution_time_seconds=elapsed,
        )

    # ── Prompt construction ──────────────────────────────────────────────

    @staticmethod
    def _build_user_prompt(
        *,
        article_markdown: str,
        target_platform: str,
        title: str,
        tags: list[str],
        article_metadata: dict[str, Any],
    ) -> str:
        """Assemble the user-turn prompt for the formatting/SNS call."""

        platform_instructions = _PLATFORM_INSTRUCTIONS.get(target_platform, "")
        tags_str = ", ".join(tags) if tags else "(none)"
        meta_str = json.dumps(article_metadata, ensure_ascii=False, default=str)

        return (
            f"Convert the following Markdown article for publication on "
            f"**{target_platform}**.\n\n"
            f"Article title: {title}\n"
            f"Tags: {tags_str}\n"
            f"Full metadata: {meta_str}\n\n"
            f"<platform_instructions>\n{platform_instructions}\n"
            f"</platform_instructions>\n\n"
            "Tasks:\n"
            "1. **formatted_content** -- Rewrite / reformat the Markdown into the "
            "platform-optimized format described above.  Preserve the article's "
            "substance and SEO intent.\n"
            "2. **sns_posts** -- Generate two share texts:\n"
            f"   - \"twitter\": max {_TWITTER_CHAR_LIMIT} characters, include 1-3 "
            "relevant hashtags.\n"
            f"   - \"linkedin\": max {_LINKEDIN_CHAR_LIMIT} characters, professional "
            "tone, include a short hook and call-to-action.\n"
            "3. **email_summary** -- A concise newsletter summary "
            f"(max {_EMAIL_SUMMARY_LIMIT} characters) with a compelling subject-line "
            "suggestion.\n\n"
            "Return your output as a JSON object with exactly these keys:\n"
            "- \"formatted_content\": string\n"
            "- \"sns_posts\": {\"twitter\": \"...\", \"linkedin\": \"...\"}\n"
            "- \"email_summary\": string\n\n"
            "Return ONLY the JSON object -- no extra commentary.\n\n"
            f"<source_article>\n{article_markdown}\n</source_article>"
        )

    # ── Response parsing ─────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw_text: str, platform: str) -> dict[str, Any]:
        """Best-effort parse of the LLM JSON response."""
        try:
            data = extract_json(raw_text, allow_truncated=True)
            return {
                "formatted_content": str(data.get("formatted_content", "")),
                "sns_posts": {
                    "twitter": str(data.get("sns_posts", {}).get("twitter", "")),
                    "linkedin": str(data.get("sns_posts", {}).get("linkedin", "")),
                },
                "email_summary": str(data.get("email_summary", "")),
            }
        except (ValueError, json.JSONDecodeError, AttributeError):
            logger.warning(
                "publisher_json_parse_failed",
                raw_length=len(raw_text),
                platform=platform,
            )
            return {
                "formatted_content": raw_text,
                "sns_posts": {"twitter": "", "linkedin": ""},
                "email_summary": "",
            }

    # ── Platform publishing stubs ────────────────────────────────────────

    async def _publish_to_platform(
        self,
        *,
        platform: str,
        formatted_content: str,
        title: str,
        tags: list[str],
        article_metadata: dict[str, Any],
    ) -> str | None:
        """Dispatch to the appropriate platform API method.

        Returns the published URL on success, or ``None`` if credentials are
        missing / the call is skipped.
        """
        dispatch = {
            "note": self._publish_to_note,
            "medium": self._publish_to_medium,
            "wordpress": self._publish_to_wordpress,
            "zenn": self._publish_to_zenn,
            "hatena": self._publish_to_hatena,
        }
        handler = dispatch.get(platform)
        if handler is None:
            return None
        return await handler(
            formatted_content=formatted_content,
            title=title,
            tags=tags,
            article_metadata=article_metadata,
        )

    # -- note.com ----------------------------------------------------------

    async def _publish_to_note(
        self,
        *,
        formatted_content: str,
        title: str,
        tags: list[str],
        article_metadata: dict[str, Any],
    ) -> str | None:
        """Publish to note.com via their API.

        note's public API is limited; this stub prepares the request payload
        and will POST when a stable endpoint is available.
        """
        if not settings.note_api_token:
            self._log.info("note_publish_skipped", reason="no API token configured")
            return None

        # note API endpoint (draft creation)
        url = "https://note.com/api/v2/notes"
        headers = {
            "Authorization": f"Bearer {settings.note_api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "title": title,
            "body": formatted_content,
            "status": "draft",
            "tags": tags[:5],  # note allows up to 5 tags
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        note_url = data.get("data", {}).get("note_url")
        self._log.info("note_publish_success", url=note_url)
        return note_url

    # -- Medium ------------------------------------------------------------

    async def _publish_to_medium(
        self,
        *,
        formatted_content: str,
        title: str,
        tags: list[str],
        article_metadata: dict[str, Any],
    ) -> str | None:
        """Publish to Medium via their API.

        Uses the documented ``/v1/users/{authorId}/posts`` endpoint.
        """
        if not settings.medium_api_token:
            self._log.info("medium_publish_skipped", reason="no API token configured")
            return None

        headers = {
            "Authorization": f"Bearer {settings.medium_api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Step 1: resolve the authenticated user ID.
        async with httpx.AsyncClient(timeout=30.0) as client:
            me_resp = await client.get(
                "https://api.medium.com/v1/me", headers=headers
            )
            me_resp.raise_for_status()
            user_id = me_resp.json()["data"]["id"]

            # Step 2: create post as draft.
            payload = {
                "title": title,
                "contentFormat": "markdown",
                "content": formatted_content,
                "tags": tags[:5],  # Medium allows up to 5 tags
                "publishStatus": "draft",
            }
            post_resp = await client.post(
                f"https://api.medium.com/v1/users/{user_id}/posts",
                headers=headers,
                json=payload,
            )
            post_resp.raise_for_status()
            post_data = post_resp.json()

        medium_url = post_data.get("data", {}).get("url")
        self._log.info("medium_publish_success", url=medium_url)
        return medium_url

    # -- WordPress ---------------------------------------------------------

    async def _publish_to_wordpress(
        self,
        *,
        formatted_content: str,
        title: str,
        tags: list[str],
        article_metadata: dict[str, Any],
    ) -> str | None:
        """Publish to a self-hosted WordPress site via the REST API.

        Uses Basic Auth (Application Passwords) against ``/wp-json/wp/v2/posts``.
        """
        if not settings.wordpress_url or not settings.wordpress_username:
            self._log.info("wordpress_publish_skipped", reason="no WP credentials configured")
            return None

        api_url = f"{settings.wordpress_url.rstrip('/')}/wp-json/wp/v2/posts"
        payload = {
            "title": title,
            "content": formatted_content,
            "status": "draft",
            "format": "standard",
        }

        # Attach categories / tags from metadata if provided.
        if category_ids := article_metadata.get("wp_category_ids"):
            payload["categories"] = category_ids
        if tag_ids := article_metadata.get("wp_tag_ids"):
            payload["tags"] = tag_ids

        auth = (settings.wordpress_username, settings.wordpress_password)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(api_url, json=payload, auth=auth)
            resp.raise_for_status()
            data = resp.json()

        wp_url = data.get("link")
        self._log.info("wordpress_publish_success", url=wp_url)
        return wp_url

    # -- Zenn --------------------------------------------------------------

    async def _publish_to_zenn(
        self,
        *,
        formatted_content: str,
        title: str,
        tags: list[str],
        article_metadata: dict[str, Any],
    ) -> str | None:
        """Prepare content for Zenn.dev publication.

        Zenn uses a Git-based workflow (articles are Markdown files pushed to
        a connected GitHub repository).  This stub formats the content with
        proper front-matter but does not perform the git push itself.
        """
        self._log.info(
            "zenn_publish_skipped",
            reason="Zenn uses git-based publishing; content formatted but not pushed",
        )
        # In a full implementation this would write the file to the Zenn
        # repo directory and commit/push via the git integration.
        return None

    # -- Hatena Blog -------------------------------------------------------

    async def _publish_to_hatena(
        self,
        *,
        formatted_content: str,
        title: str,
        tags: list[str],
        article_metadata: dict[str, Any],
    ) -> str | None:
        """Prepare content for Hatena Blog publication.

        Hatena Blog supports the AtomPub API for programmatic posting.
        This stub outlines the request structure but does not execute it
        without valid credentials.
        """
        self._log.info(
            "hatena_publish_skipped",
            reason="Hatena AtomPub credentials not configured",
        )
        # In a full implementation this would POST to the Hatena AtomPub
        # endpoint with WSSE authentication.
        return None


# ── Platform-specific formatting instructions ────────────────────────────────

_PLATFORM_INSTRUCTIONS: dict[str, str] = {
    "note": (
        "note.com formatting guidelines:\n"
        "- Use note-compatible Markdown (headers, bold, italic, lists, block quotes).\n"
        "- note does not render raw HTML; remove any HTML tags.\n"
        "- Image references should use ![alt](url) syntax.\n"
        "- Keep paragraphs concise; note readers prefer scannable content.\n"
        "- Add a compelling opening hook in the first 140 characters (shown in preview).\n"
        "- Use horizontal rules (---) sparingly to separate major sections.\n"
        "- The article language is typically Japanese."
    ),
    "medium": (
        "Medium formatting guidelines:\n"
        "- Use standard Markdown; Medium's importer handles it well.\n"
        "- Use ## for section headings (Medium maps # to the title automatically).\n"
        "- Block quotes (>) render as pull-quotes -- use for key take-aways.\n"
        "- Code blocks (```) are supported with syntax highlighting.\n"
        "- Avoid inline HTML; Medium strips most of it.\n"
        "- Embed links as inline Markdown links [text](url) rather than raw URLs.\n"
        "- Keep paragraphs to 3-4 sentences for optimal readability."
    ),
    "wordpress": (
        "WordPress formatting guidelines:\n"
        "- Output as HTML (WordPress Gutenberg block format preferred).\n"
        "- Wrap paragraphs in <p> tags.\n"
        "- Use <!-- wp:heading --> block comments for headings where possible.\n"
        "- Images: use <!-- wp:image --> blocks with <figure> and <img> tags.\n"
        "- Lists: standard <ul>/<ol> with <li> items.\n"
        "- Add id attributes to headings for table-of-contents anchor links.\n"
        "- Include a <!-- wp:separator --> block between major sections."
    ),
    "zenn": (
        "Zenn.dev formatting guidelines:\n"
        "- Use Zenn-flavoured Markdown with YAML front-matter.\n"
        "- Front-matter must include: title, emoji, type (tech/idea), topics, published.\n"
        "- Example front-matter:\n"
        "  ---\n"
        "  title: \"Article Title\"\n"
        "  emoji: \"📝\"\n"
        "  type: \"tech\"\n"
        "  topics: [\"real-estate\", \"proptech\"]\n"
        "  published: false\n"
        "  ---\n"
        "- Use ::: message (info/warn/alert) for callout boxes.\n"
        "- Code blocks support language specifiers and file names (```ts:filename.ts).\n"
        "- Embed links with Zenn's card syntax: simply paste the URL on its own line."
    ),
    "hatena": (
        "Hatena Blog formatting guidelines:\n"
        "- Use Hatena Markdown mode (similar to standard Markdown with extensions).\n"
        "- Headings use standard # syntax; ## maps to h3 in Hatena's hierarchy.\n"
        "- Footnotes: use (( )) for Hatena-style footnotes.\n"
        "- Embed links with [url:title] or standard Markdown link syntax.\n"
        "- Categories are added via metadata, not in the body.\n"
        "- Use > for block quotes (renders with Hatena styling).\n"
        "- Table syntax follows standard Markdown pipe tables.\n"
        "- The article language is typically Japanese."
    ),
}

# ── System prompt (module-level constant) ────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a **content publishing specialist** for a real-estate content \
marketing platform.  Your job is to take a finalised Markdown article and \
produce three outputs:

1. **Platform-formatted content** -- the article rewritten / reformatted to \
match the conventions and technical requirements of the target publishing \
platform.  You must follow the platform-specific instructions exactly.

2. **SNS share posts** -- short, engaging texts optimised for Twitter/X and \
LinkedIn that promote the article and encourage click-through.

3. **Email newsletter summary** -- a concise digest-style summary suitable \
for inclusion in an email newsletter, with a suggested subject line.

Strict rules:
- Preserve the article's substance, data, and SEO intent during formatting.
- Do NOT add or invent new information.
- Respect each platform's character limits and supported syntax.
- Twitter text MUST be <= 280 characters including hashtags.
- LinkedIn text should be professional and include a call-to-action.
- Email summary should include a subject-line suggestion on the first line \
(prefixed with "Subject: ").
- You MUST return valid JSON matching the schema described in the user \
prompt -- no extra text outside the JSON object.
"""
