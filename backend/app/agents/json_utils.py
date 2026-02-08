"""Shared utilities for agent JSON parsing and repair."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str, *, allow_truncated: bool = False) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from LLM text.

    Handles:
    - Pure JSON
    - JSON wrapped in ```json ... ``` fences (including unclosed fences)
    - JSON preceded/followed by commentary text
    - Truncated JSON (when allow_truncated=True): repairs by closing
      open strings, arrays, and objects
    """
    text = text.strip()

    # 1. Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Try to extract from markdown code fences (including unclosed fences)
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)(?:\n?\s*```|$)", text, re.DOTALL)
    if fence_match:
        inner = fence_match.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            if allow_truncated and inner:
                repaired = _repair_truncated_json(inner)
                if repaired is not None:
                    return repaired

    # 3. Try to find the outermost { ... } block
    brace_match = re.search(r"\{", text)
    if brace_match:
        start_idx = brace_match.start()
        # Find the matching closing brace by counting depth
        depth = 0
        end_idx = start_idx
        for i in range(start_idx, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        if end_idx > start_idx:
            try:
                return json.loads(text[start_idx:end_idx])
            except json.JSONDecodeError:
                pass

        # If we have an opening brace but no matching close, try repair
        if allow_truncated:
            json_text = text[start_idx:]
            repaired = _repair_truncated_json(json_text)
            if repaired is not None:
                return repaired

    raise ValueError(f"No valid JSON found in LLM response ({len(text)} chars)")


def _repair_truncated_json(text: str) -> dict[str, Any] | None:
    """Attempt to repair truncated JSON by closing open structures.

    This is a best-effort repair for JSON that was cut off mid-stream
    (e.g. due to max_tokens). It closes open strings, arrays, and objects.
    """
    # Remove any trailing incomplete escape or partial token
    text = text.rstrip()
    if text.endswith("\\"):
        text = text[:-1]

    # Close any open string
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string

    if in_string:
        text += '"'

    # Remove trailing comma (invalid before closing bracket)
    text = re.sub(r",\s*$", "", text)

    # Count and close open brackets/braces
    open_braces = 0
    open_brackets = 0
    in_str = False
    esc = False
    for ch in text:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
        if in_str:
            continue
        if ch == "{":
            open_braces += 1
        elif ch == "}":
            open_braces -= 1
        elif ch == "[":
            open_brackets += 1
        elif ch == "]":
            open_brackets -= 1

    text += "]" * max(0, open_brackets)
    text += "}" * max(0, open_braces)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
