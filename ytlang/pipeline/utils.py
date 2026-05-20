"""Shared pipeline utilities — LLM client, JSON parsing, video ID extraction."""
from __future__ import annotations

import re
import json


def make_client():
    """Create an xAI SDK client (reads XAI_API_KEY from env)."""
    try:
        from xai_sdk import Client
    except ImportError:
        raise ImportError("pip install xai-sdk")
    return Client()


def parse_llm_json(raw: str) -> dict | list:
    """Parse LLM response text as JSON, stripping code fences and trailing commas.

    If the JSON is truncated (unterminated strings/brackets), attempts repair
    by closing open strings, removing the incomplete trailing element, and
    balancing brackets.
    """
    cleaned = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw.strip())
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        repaired = _repair_truncated_json(cleaned)
        return json.loads(repaired)


def _repair_truncated_json(s: str) -> str:
    """Best-effort repair of truncated JSON by closing open structures."""
    in_string = False
    last_quote = -1
    stack: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and in_string:
            i += 2
            continue
        if c == '"':
            in_string = not in_string
            last_quote = i
        elif not in_string:
            if c in '{[':
                stack.append('}' if c == '{' else ']')
            elif c in '}]' and stack:
                stack.pop()
        i += 1

    if in_string and last_quote >= 0:
        # Close the open string, then remove the incomplete trailing element
        s = s[:last_quote] + '"'
        s = re.sub(r',\s*"[^"]*"\s*$', '', s)
        # Rescan brackets on the shortened string
        stack.clear()
        in_str = False
        for c in s:
            if c == '"':
                in_str = not in_str
            elif not in_str:
                if c in '{[':
                    stack.append('}' if c == '{' else ']')
                elif c in '}]' and stack:
                    stack.pop()

    s = re.sub(r',\s*$', '', s.rstrip())
    s += ''.join(reversed(stack))
    return s


def parse_video_id(url: str) -> str:
    """Extract 11-char video ID from any standard YouTube URL format."""
    m = re.search(
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
        url,
    )
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    raise ValueError(f"Could not extract video ID from: {url}")
