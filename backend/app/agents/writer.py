"""Writer Agent -- the most important agent in the knock knock AI pipeline.

The Writer produces high-quality, human-readable content that passes AI
detection checks and resonates with the target audience.  It encodes five
quality principles directly into its system prompt and generates articles
section-by-section for maximum coherence and depth.
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
# Constants
# ---------------------------------------------------------------------------

_BRAND_VOICE_GUIDELINES = """\
## knock knock AI Brand Voice Guidelines

**Brand personality**: Knowledgeable yet approachable. We are the friendly \
expert who makes complex AI and content-marketing topics accessible to \
everyone -- from startup founders to seasoned marketers.

**Tone attributes**:
- Warm and conversational, never robotic or overly formal
- Confident but not arrogant -- we share expertise with humility
- Action-oriented -- every paragraph should move the reader towards a \
  concrete takeaway
- Culturally aware -- when writing in Japanese, honour natural Japanese \
  sentence flow and avoid awkward translationese

**Voice do's**:
- Use first-person plural ("we", "us") when representing knock knock AI
- Address the reader directly ("you", "your")
- Include real-world examples, data points, and case studies wherever possible
- Break up long passages with sub-headings, bullet lists, and callout boxes
- End sections with a brief bridge sentence that leads into the next topic

**Voice don'ts**:
- Never use filler phrases ("In today's fast-paced world...", "It goes \
  without saying...")
- Avoid passive voice unless it genuinely improves readability
- Do not over-use exclamation marks
- Never claim capabilities we do not actually have
"""

_CTA_GUIDELINES = """\
## knock knock AI CTA (Call-to-Action) Strategy

This article is created to **promote knock knock AI** and drive traffic to \
our product. You MUST naturally weave CTA links into the article using the \
following rules:

**CTA URL**: https://www.knock-knock-ai.com/

**Placement rules** (MANDATORY):
1. **Introduction CTA**: In the introduction, mention knock knock AI as a \
   solution and include ONE clickable link. Example (Japanese): \
   「そんな課題を解決するのが[knock knock AI](https://www.knock-knock-ai.com/)です。」
2. **Mid-article CTAs**: Insert a CTA link in **at least 2 body sections** \
   where it fits naturally in context. Do NOT force it -- weave it into the \
   argument. Examples:
   - 「[knock knock AI](https://www.knock-knock-ai.com/)なら、この作業を自動化できます」
   - 「詳しくは[knock knock AI公式サイト](https://www.knock-knock-ai.com/)をご覧ください」
   - 「実際に[knock knock AI](https://www.knock-knock-ai.com/)を導入した企業では〜」
3. **Closing CTA**: The final section MUST end with a strong CTA block -- \
   a brief paragraph inviting the reader to visit knock knock AI with a \
   clickable link. Example:
   「AIを活用したコンテンツマーケティングに興味がある方は、ぜひ\
   [knock knock AI](https://www.knock-knock-ai.com/)をお試しください。」

**CTA style rules**:
- Links MUST be Markdown format: [表示テキスト](https://www.knock-knock-ai.com/)
- The anchor text should be natural and varied -- do NOT always use the same \
  phrasing. Use different expressions each time (e.g., "knock knock AI", \
  "knock knock AI公式サイト", "こちら", "knock knock AIの詳細").
- CTAs must feel like a natural part of the article flow, NOT like an \
  advertisement. Tie knock knock AI's value to the specific topic being \
  discussed in that section.
- Position knock knock AI as the expert/solution provider for the topic.
"""

_NOTE_ARTICLE_GUIDELINES = """\
## note記事ライティングガイドライン

この記事は「noteのビジネス記事」として公開される。読者がスマホで"流し読み"しても \
要点が理解でき、読後に行動したくなる記事を目指す。

### 絶対条件
- 事実関係は捏造しない。数字・制度・統計などは、根拠がないなら「推測」「一例」と明記する
- 誇大表現や煽りで釣らない。長期的な信頼を優先する
- 読者の時間を奪わない。結論・要点を早めに出す
- "誰でも簡単に""絶対""100%"など、根拠のない断定は禁止
- 一般論だけで埋めない。必ず具体例・比較・失敗談・反証を入れる

### 文章スタイル
- 口語寄りだが、馴れ馴れしすぎない（ビジネス読者に不快感を与えない）
- 1段落は1〜3文。改行を多めにして、視線移動を軽くする
- 見出しは情報量の多い言葉から始める（見出しだけ追っても流れが分かるように）
- 抽象語はできるだけ具体例に落とす（場面・人物・行動・会話・数字・期間など）

### 記事構成の型
- 冒頭30秒で読者が"読む価値"を理解できるよう、**フック → 約束 → 結論**の順で書く
- 本文の各セクションは「結論 → 理由 → 手順 → 具体例 → 注意点」の流れで展開する
- 最終セクションの後に必ず以下2つを追加する:
  1. **まとめ**（3〜5行の要約）
  2. **今日やること**（読者がすぐ実行できる最小の一歩を1〜3個、箇条書き）

### 見出しルール
- H2見出しは4〜6個を目安
- 見出しだけ読んでも記事の流れが分かるようにする
- 見出しに数字や具体的な情報を含める（例: ×「効果について」→ ○「導入3ヶ月で問い合わせ2倍になった理由」）
"""

_FIVE_QUALITY_PRINCIPLES = """\
You MUST internalise and apply the following five quality principles in \
every sentence you write.  These are non-negotiable.

### Principle 1 -- Conversational Natural Tone (語りかけるような口調)
Write as if you are sitting across from the reader, explaining something \
you are genuinely passionate about.  Vary between short, punchy sentences \
and longer, flowing ones.  Use rhetorical questions, gentle humour, and \
direct address ("you") to keep the reader engaged.  When writing in \
Japanese, prefer spoken-style sentence endings (〜ですよね, 〜なんです, \
〜してみてください) over stiff written-style endings.

### Principle 2 -- Specificity with Evidence (具体性とエビデンス)
Every claim must be backed by a concrete detail: a number, a date, a named \
source, or a real-world example.  Replace vague qualifiers ("many", \
"significantly", "often") with precise data from the research report.  If \
the research does not contain a specific figure, rephrase the claim so it \
does not over-promise.

### Principle 3 -- Sentence Structure Diversity (文構造の多様化)
Monotonous sentence patterns are the #1 signal of AI-generated text.  \
Deliberately alternate between:
  - Simple declarative sentences (Subject-Verb-Object)
  - Compound sentences joined by conjunctions
  - Sentences that open with a dependent clause or prepositional phrase
  - One-word or two-word fragment sentences for emphasis
  - Occasional parenthetical asides or em-dashes for voice
Aim for a mix where no two consecutive sentences share the same structure.

### Principle 4 -- Experience and Unique Perspective Injection (体験と独自視点)
The content must feel like it was written by someone who has *lived* the \
topic, not merely researched it.  Weave in first-person anecdotes (even \
composited ones based on common industry experiences), opinionated takes, \
and "lessons learned" framing.  Use phrases like "In our experience...", \
"One mistake we see repeatedly is...", "Here is what most guides will not \
tell you...".

### Principle 5 -- Visual Scannability Optimisation (視覚的スキャナビリティ)
Structure the content for scanners *and* deep readers:
  - H2 / H3 headings every 200-350 words
  - Bullet or numbered lists for any set of 3+ items
  - Bold key terms on first mention
  - Short paragraphs (3-5 sentences max)
  - A TL;DR / key-takeaway box at the beginning or end of each major section
"""

# ---------------------------------------------------------------------------
# Section-generation prompt template
# ---------------------------------------------------------------------------

_SECTION_PROMPT_TEMPLATE = """\
You are now writing **Section {section_number}** of the article.

## Section Outline
{section_outline}

## Preceding Content So Far
{preceding_content}

## Research Report (use this as your evidence base)
{research_excerpt}

## Instructions
- Write ONLY this section.  Do NOT repeat content already written above.
- Aim for {target_word_count} words for this section.
- Start with the section heading (Markdown ## or ###). \
  見出しは情報量の多い言葉から始め、見出しだけで内容が分かるようにする。\
  数字や具体的な情報を含めること。
- Apply all five quality principles rigorously.
- note記事スタイル: セクション内は「結論 → 理由 → 具体例 → 注意点」の \
  順で展開する。抽象論ではなく場面・人物・行動・数字で語る。
- 段落は1〜3文。改行を多めにして、スマホで流し読みしやすくする。
- 根拠のない断定（"誰でも簡単に""絶対"等）は使わない。\
  数字や統計に根拠がない場合は「推測」「一例」と明記する。
- End with a natural bridge sentence that leads into the next section \
  (unless this is the final section, in which case write a compelling \
  conclusion paragraph).
- {cta_instruction}
- Output ONLY the Markdown for this section -- no meta-commentary.
"""


class WriterAgent(BaseAgent):
    """Produces long-form, high-quality content for the knock knock AI platform.

    The Writer is the single most important agent in the pipeline.  It takes
    a structured outline and a research report and generates a complete article
    section-by-section, ensuring coherence, evidence grounding, and a natural
    human voice.
    """

    # ------------------------------------------------------------------ #
    # BaseAgent abstract interface                                        #
    # ------------------------------------------------------------------ #

    @property
    def agent_name(self) -> str:
        return "writer"

    @property
    def model_name(self) -> str:
        return settings.default_writer_model

    @property
    def system_prompt(self) -> str:
        return (
            "You are the senior content writer for **knock knock AI**, an AI-driven "
            "content-marketing automation platform.  Your job is to produce articles "
            "that are indistinguishable from the best human-written content: engaging, "
            "well-researched, and optimised for both readers and search engines.\n\n"
            "CRITICAL: Every article you write serves a dual purpose -- educating the "
            "reader AND promoting knock knock AI as the go-to solution.  You must "
            "naturally position knock knock AI throughout the article.\n\n"
            f"{_BRAND_VOICE_GUIDELINES}\n\n"
            f"{_CTA_GUIDELINES}\n\n"
            f"{_NOTE_ARTICLE_GUIDELINES}\n\n"
            f"{_FIVE_QUALITY_PRINCIPLES}\n\n"
            "IMPORTANT: Output raw Markdown only.  Never wrap your output in "
            "```markdown``` fences.  Never include meta-commentary about what you "
            "are writing."
        )

    # ------------------------------------------------------------------ #
    # Main execution                                                      #
    # ------------------------------------------------------------------ #

    async def execute(self, context: AgentContext) -> AgentResult:
        """Generate a full article from an outline and research report.

        Expected ``context.input_data`` keys:

        * **outline** (``str``): Structured article outline with section
          headings and bullet points for each section.
        * **research_report** (``str``): Compiled research report with sources
          and data points.
        * **brand_voice_guidelines** (``str``, optional): Additional or
          override brand-voice notes.  Defaults to the built-in guidelines.
        * **target_language** (``str``, optional): ISO language code
          (default ``"ja"``).

        Returns an :class:`AgentResult` whose ``output_data`` contains:

        * **article_markdown** (``str``): The complete article in Markdown.
        * **word_count** (``int``): Total word / character count.
        * **sections_generated** (``int``): Number of sections written.
        """
        self._reset_token_tracking()
        start_time = time.monotonic()

        self._log.info("writer_execute_start", task_id=context.task_id)

        # ----- extract inputs from orchestrator cumulative_data ---------------
        cal = context.input_data.get("calendar_entry", {})
        plan_step = context.input_data.get("plan", {})
        research_step = context.input_data.get("research", {})

        # The planner output contains a structured outline JSON; convert to
        # readable Markdown for the writer prompt.
        outline_data = plan_step.get("outline", {})
        if isinstance(outline_data, dict) and outline_data.get("h1"):
            outline = self._outline_to_markdown(outline_data)
        else:
            outline = context.input_data.get("outline", "")

        research_report: str = (
            research_step.get("research_report", "")
            or context.input_data.get("research_report", "")
        )
        brand_voice_extra: str = context.input_data.get("brand_voice_guidelines", "")
        target_language: str = (
            cal.get("language", "")
            or context.input_data.get("target_language", "ja")
        )

        if not outline:
            return AgentResult(
                success=False,
                error_message="No outline provided in context.input_data['outline'].",
                execution_time_seconds=time.monotonic() - start_time,
            )

        # ----- parse sections from the outline --------------------------------
        sections = self._parse_outline_sections(outline)
        if not sections:
            return AgentResult(
                success=False,
                error_message="Could not parse any sections from the provided outline.",
                execution_time_seconds=time.monotonic() - start_time,
            )

        self._log.info(
            "writer_sections_parsed",
            section_count=len(sections),
            target_language=target_language,
        )

        # ----- generate article introduction ----------------------------------
        intro_markdown = await self._generate_introduction(
            outline=outline,
            research_report=research_report,
            brand_voice_extra=brand_voice_extra,
            target_language=target_language,
        )

        generated_parts: list[str] = [intro_markdown]

        # ----- iterate over body sections ------------------------------------
        for idx, section in enumerate(sections, start=1):
            preceding = "\n\n".join(generated_parts)
            section_md = await self._generate_section(
                section_number=idx,
                section_outline=section,
                preceding_content=preceding,
                research_report=research_report,
                target_language=target_language,
                is_last_section=(idx == len(sections)),
                total_sections=len(sections),
            )
            generated_parts.append(section_md)

            self._log.info(
                "writer_section_complete",
                section_number=idx,
                total_sections=len(sections),
            )

        # ----- generate closing section: まとめ + 今日やること -----------------
        closing_md = await self._generate_closing(
            preceding_content="\n\n".join(generated_parts),
            target_language=target_language,
        )
        generated_parts.append(closing_md)

        # ----- assemble final article ----------------------------------------
        article_markdown = "\n\n".join(generated_parts)
        word_count = self._count_words(article_markdown, target_language)

        elapsed = time.monotonic() - start_time
        self._log.info(
            "writer_execute_complete",
            word_count=word_count,
            sections_generated=len(sections),
            tokens_used=self._total_tokens,
            cost_usd=round(self._total_cost, 6),
            elapsed_seconds=round(elapsed, 2),
        )

        return AgentResult(
            success=True,
            output_data={
                "article_markdown": article_markdown,
                "word_count": word_count,
                "sections_generated": len(sections),
            },
            tokens_used=self._total_tokens,
            cost_usd=self._total_cost,
            execution_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------ #
    # Private helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _generate_introduction(
        self,
        *,
        outline: str,
        research_report: str,
        brand_voice_extra: str,
        target_language: str,
    ) -> str:
        """Generate the article title and introduction section."""
        lang_instruction = self._language_instruction(target_language)
        brand_section = (
            f"\n\n## Additional Brand Voice Notes\n{brand_voice_extra}"
            if brand_voice_extra
            else ""
        )

        user_message = (
            "Write the **title** (as a Markdown H1) and the **introduction** for the "
            "following article.\n\n"
            "## Introduction Structure (note記事スタイル)\n"
            "冒頭30秒で読む価値を伝えるため、以下の順で書くこと:\n"
            "1. **フック** -- 読者の悩みや疑問に共感する1〜2文（「〜で困っていませんか？」等）\n"
            "2. **約束** -- この記事を読むと何が得られるかを明示する\n"
            "3. **結論の先出し** -- 記事の核心を1〜2文で端的に述べる\n"
            "4. **CTA** -- knock knock AIをソリューションとして自然に紹介し、"
            "リンクを1つ挿入: [knock knock AI](https://www.knock-knock-ai.com/)\n\n"
            "段落は1〜3文ずつ、改行を多めに。Aim for 150-250 words.\n\n"
            f"## Full Article Outline\n{outline}\n\n"
            f"## Research Report\n{research_report}\n\n"
            f"{lang_instruction}"
            f"{brand_section}\n\n"
            "Output ONLY the Markdown for the title and introduction -- nothing else."
        )

        response = await self._call_llm(
            [{"role": "user", "content": user_message}],
            max_tokens=2048,
            temperature=0.75,
        )
        return self._text_from_response(response)

    async def _generate_section(
        self,
        *,
        section_number: int,
        section_outline: str,
        preceding_content: str,
        research_report: str,
        target_language: str,
        is_last_section: bool,
        total_sections: int = 0,
    ) -> str:
        """Generate a single body section of the article."""
        # Truncate preceding content to keep within context limits while
        # preserving the most recent context (last ~3000 chars) plus the
        # very beginning (~1000 chars) for title/intro continuity.
        preceding_excerpt = self._smart_truncate(preceding_content, max_chars=4000)
        research_excerpt = self._smart_truncate(research_report, max_chars=4000)

        target_word_count = "300-400"
        if is_last_section:
            target_word_count = "200-350 (include a compelling conclusion)"

        # Determine CTA instruction based on section position
        cta_instruction = self._get_section_cta_instruction(
            section_number, total_sections or section_number, is_last_section
        )

        lang_instruction = self._language_instruction(target_language)

        user_message = _SECTION_PROMPT_TEMPLATE.format(
            section_number=section_number,
            section_outline=section_outline,
            preceding_content=preceding_excerpt,
            research_excerpt=research_excerpt,
            target_word_count=target_word_count,
            cta_instruction=cta_instruction,
        ) + f"\n\n{lang_instruction}"

        response = await self._call_llm(
            [{"role": "user", "content": user_message}],
            max_tokens=4096,
            temperature=0.72,
        )
        return self._text_from_response(response)

    async def _generate_closing(
        self,
        *,
        preceding_content: str,
        target_language: str,
    ) -> str:
        """Generate the note-style closing: まとめ + 今日やること."""
        preceding_excerpt = self._smart_truncate(preceding_content, max_chars=5000)
        lang_instruction = self._language_instruction(target_language)

        user_message = (
            "記事本文は完成しました。以下の記事全体を踏まえて、"
            "note記事の締めくくりを書いてください。\n\n"
            f"## これまでの記事内容\n{preceding_excerpt}\n\n"
            "## 出力する内容（この順番で）\n\n"
            "### 1. まとめ（H2見出し「まとめ」で始める）\n"
            "- 記事全体の要点を3〜5行で簡潔にまとめる\n"
            "- 読者が「読んでよかった」と思える振り返りにする\n"
            "- knock knock AIへのCTAリンクを1つ自然に含める: "
            "[knock knock AI](https://www.knock-knock-ai.com/)\n\n"
            "### 2. 今日やること（H2見出し「今日やること」で始める）\n"
            "- 読者がすぐ実行できる最小の一歩を1〜3個、箇条書きで提示する\n"
            "- 具体的で、ハードルが低く、行動に移しやすいものにする\n"
            "- 例:「まずは○○を10分だけ試してみる」「○○のアカウントを作成する」等\n\n"
            f"{lang_instruction}\n\n"
            "Output ONLY the Markdown for まとめ and 今日やること -- no meta-commentary."
        )

        response = await self._call_llm(
            [{"role": "user", "content": user_message}],
            max_tokens=2048,
            temperature=0.72,
        )
        return self._text_from_response(response)

    # ------------------------------------------------------------------ #
    # Outline conversion                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _outline_to_markdown(outline_data: dict) -> str:
        """Convert a structured planner JSON outline to Markdown."""
        lines: list[str] = []
        h1 = outline_data.get("h1", "Untitled")
        lines.append(f"# {h1}\n")

        for section in outline_data.get("sections", []):
            heading = section.get("heading", "")
            level = section.get("heading_level", 2)
            prefix = "#" * level
            lines.append(f"{prefix} {heading}")

            instructions = section.get("writing_instructions", "")
            if instructions:
                lines.append(f"_{instructions}_\n")

            for point in section.get("key_points", []):
                lines.append(f"- {point}")

            for sub in section.get("subsections", []):
                sub_heading = sub.get("heading", "")
                sub_level = sub.get("heading_level", 3)
                sub_prefix = "#" * sub_level
                lines.append(f"\n{sub_prefix} {sub_heading}")
                sub_instructions = sub.get("writing_instructions", "")
                if sub_instructions:
                    lines.append(f"_{sub_instructions}_\n")
                for point in sub.get("key_points", []):
                    lines.append(f"- {point}")

            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Outline parsing                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_outline_sections(outline: str) -> list[str]:
        """Split a Markdown outline into individual section chunks.

        Looks for H2 (``##``) boundaries.  Each chunk includes the heading
        and all content up to (but not including) the next H2.  The very
        first chunk (before any H2) is considered the introduction and is
        *excluded* -- it will be generated separately.
        """
        # Split on H2 headings, keeping the delimiter
        parts = re.split(r"(?=^##\s)", outline, flags=re.MULTILINE)
        sections: list[str] = []
        for part in parts:
            stripped = part.strip()
            if stripped and stripped.startswith("## "):
                sections.append(stripped)
        return sections

    # ------------------------------------------------------------------ #
    # Utility helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _smart_truncate(text: str, max_chars: int) -> str:
        """Truncate long text while preserving start and end context."""
        if len(text) <= max_chars:
            return text

        # Keep the first portion and last portion to maintain context
        head_size = max_chars // 3
        tail_size = max_chars - head_size - 40  # 40 chars for the separator
        return (
            text[:head_size]
            + "\n\n[... content trimmed for context window ...]\n\n"
            + text[-tail_size:]
        )

    @staticmethod
    def _count_words(text: str, language: str) -> int:
        """Estimate word count.

        For CJK languages (ja, zh, ko), count characters (excluding spaces
        and punctuation) since word boundaries are not space-delimited.
        For other languages, split on whitespace.
        """
        if language in ("ja", "zh", "ko"):
            # Count meaningful characters (letters, digits, CJK ideographs)
            return len(re.findall(r"[\w]", text, flags=re.UNICODE))
        return len(text.split())

    @staticmethod
    def _language_instruction(target_language: str) -> str:
        """Return a language-specific writing instruction."""
        instructions: dict[str, str] = {
            "ja": (
                "IMPORTANT: Write the ENTIRE output in natural, fluent Japanese.  "
                "Use spoken-style sentence endings where appropriate (〜です, "
                "〜ですよね, 〜してみましょう).  Avoid translationese.  "
                "Technical terms may remain in English with a Japanese explanation "
                "in parentheses on first use."
            ),
            "en": (
                "Write the entire output in clear, engaging American English."
            ),
            "zh": (
                "Write the entire output in Simplified Chinese (简体中文).  "
                "Use a conversational and professional tone."
            ),
            "ko": (
                "Write the entire output in natural Korean (한국어).  "
                "Use a friendly, professional register."
            ),
        }
        return instructions.get(
            target_language,
            f"Write the entire output in the language with ISO code '{target_language}'.",
        )

    @staticmethod
    def _get_section_cta_instruction(
        section_number: int, total_sections: int, is_last_section: bool
    ) -> str:
        """Return a CTA instruction tailored to the section's position."""
        if is_last_section:
            return (
                "MANDATORY: This is the final section. End with a strong CTA "
                "paragraph that invites readers to try knock knock AI. Include "
                "a clickable Markdown link: "
                "[knock knock AI](https://www.knock-knock-ai.com/). "
                "Make it feel like a natural conclusion, not an ad."
            )

        # Insert CTAs in roughly the middle sections (e.g., sections 2 and 4
        # out of 6, or section 2 out of 3).  For short articles, every other
        # section gets a CTA.
        mid_point = max(1, total_sections // 3)
        if section_number % mid_point == 0 or section_number == 2:
            return (
                "Include ONE natural CTA link to knock knock AI in this section. "
                "Use Markdown format: [表示テキスト](https://www.knock-knock-ai.com/). "
                "Tie it to the specific topic of this section -- position knock knock AI "
                "as a solution or resource. Vary the anchor text from previous CTAs."
            )

        return (
            "No CTA link required in this section, but you may reference "
            "knock knock AI naturally if it fits the context."
        )
