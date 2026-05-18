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
    """Parse LLM response text as JSON, stripping code fences and trailing commas."""
    cleaned = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw.strip())
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    return json.loads(cleaned)


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
