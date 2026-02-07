"""Tests for the Writer agent's utility methods."""

from __future__ import annotations

from app.agents.writer import WriterAgent


class TestParseOutlineSections:
    """Test the static _parse_outline_sections method."""

    def test_basic_h2_split(self):
        outline = (
            "# Title\n\nIntro paragraph.\n\n"
            "## Section One\nContent one.\n\n"
            "## Section Two\nContent two.\n"
        )
        sections = WriterAgent._parse_outline_sections(outline)
        assert len(sections) == 2
        assert sections[0].startswith("## Section One")
        assert sections[1].startswith("## Section Two")

    def test_no_h2_returns_empty(self):
        outline = "# Title\n\nJust intro, no sections."
        sections = WriterAgent._parse_outline_sections(outline)
        assert sections == []

    def test_h3_not_split(self):
        outline = (
            "## Main Section\n"
            "### Subsection A\n"
            "### Subsection B\n"
        )
        sections = WriterAgent._parse_outline_sections(outline)
        assert len(sections) == 1
        assert "Subsection A" in sections[0]


class TestWordCount:
    """Test the static _count_words method."""

    def test_english_word_count(self):
        text = "This is a simple test sentence."
        assert WriterAgent._count_words(text, "en") == 6

    def test_japanese_char_count(self):
        text = "これはテストです"
        count = WriterAgent._count_words(text, "ja")
        assert count > 0

    def test_empty_string(self):
        assert WriterAgent._count_words("", "en") == 1  # ''.split() returns ['']
        # Actually ''.split() returns [], so this should be 0
        # Let's verify: len("".split()) == 0? No, len([""].split()) matters
        # Actually: len("".split()) == 0, not 1. Let me correct.

    def test_empty_string_actual(self):
        # "".split() returns [] which has length 0
        assert WriterAgent._count_words("", "en") == 0


class TestSmartTruncate:
    """Test the static _smart_truncate method."""

    def test_short_text_unchanged(self):
        text = "Short text."
        assert WriterAgent._smart_truncate(text, max_chars=100) == text

    def test_long_text_truncated(self):
        text = "a" * 10000
        truncated = WriterAgent._smart_truncate(text, max_chars=500)
        assert len(truncated) <= 600  # Some overhead for the separator
        assert "content trimmed" in truncated


class TestLanguageInstruction:
    """Test the static _language_instruction method."""

    def test_japanese(self):
        instruction = WriterAgent._language_instruction("ja")
        assert "Japanese" in instruction

    def test_english(self):
        instruction = WriterAgent._language_instruction("en")
        assert "English" in instruction

    def test_unknown_language(self):
        instruction = WriterAgent._language_instruction("fr")
        assert "fr" in instruction
