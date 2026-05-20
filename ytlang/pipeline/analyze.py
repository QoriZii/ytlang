"""Analyze bilingual transcript with Grok API to produce vocab and content notes.

Makes a single structured API call; returns data ready to merge into LessonData.
"""
from __future__ import annotations

import json
import re
from typing import List, Tuple

from ytlang import config
from ytlang.models import TranscriptEntry, VocabEntry
from ytlang.pipeline.utils import make_client, parse_llm_json
from ytlang.languages import DEFAULT_SOURCE_LANG, DEFAULT_NATIVE_LANG


def _format_transcript(entries: List[TranscriptEntry]) -> str:
    lines = []
    for e in entries:
        m, s = divmod(e.seconds, 60)
        lines.append(f"[{m}:{s:02d}] en: {e.en!r} | zh: {e.zh!r}")
    return "\n".join(lines)


def _target_per_level(transcript: List[TranscriptEntry]) -> int:
    if not transcript:
        return 5
    duration_minutes = transcript[-1].seconds / 60
    return max(3, round(duration_minutes / 3 * 3.5))


# ── API call ───────────────────────────────────────────────────────────────────

def analyze(
    title: str,
    channel: str,
    duration: str,
    transcript: List[TranscriptEntry],
    source_lang: str = DEFAULT_SOURCE_LANG,
    native_lang: str = DEFAULT_NATIVE_LANG,
) -> Tuple[str, List[dict], List[dict], List[dict], List[VocabEntry], List[TranscriptEntry]]:
    """Call Grok API to produce video_brief, key_points, quiz_questions, situation_cards, vocab, and annotated transcript.

    Returns:
        (video_brief, key_points, quiz_questions, situation_cards, vocab_entries, transcript_entries_with_notes)

    Raises:
        ValueError: if XAI_API_KEY is not set
        openai.APIError: on API failure
    """
    if not config.XAI_API_KEY:
        raise ValueError(
            "XAI_API_KEY is not set. Export it: export XAI_API_KEY=xai-..."
        )

    from xai_sdk.chat import system, user
    from ytlang.prompts import load_prompts
    from ytlang.languages import lang_name

    prompts = load_prompts(source_lang, native_lang)

    client = make_client()

    target = _target_per_level(transcript)
    duration_minutes = transcript[-1].seconds / 60 if transcript else 0

    prompt = prompts["analyze_user"].format(
        title=title,
        channel=channel,
        duration=duration,
        duration_minutes=duration_minutes,
        target_per_level=target,
        transcript_text=_format_transcript(transcript),
        native_lang_name=lang_name(native_lang),
    )

    chat = client.chat.create(
        model=config.XAI_MODEL,
        max_tokens=16384,
        response_format="json_object",
    )
    chat.append(system(prompts["analyze_system"]))
    chat.append(user(prompt))
    response = chat.sample()

    data = parse_llm_json(response.content)

    video_brief: str = data.get("video_brief", "")

    key_points: list[dict] = data.get("key_points", [])

    quiz_questions: list[dict] = data.get("quiz_questions", [])

    situation_cards: list[dict] = data.get("situation_cards", [])

    vocab = [VocabEntry.from_dict(v) for v in data.get("vocab", [])]

    # Build a seconds→note lookup from transcript_notes
    notes_by_seconds: dict[int, str] = {
        int(n["seconds"]): n["note"]
        for n in data.get("transcript_notes", [])
        if n.get("note")
    }

    annotated = [
        TranscriptEntry(
            seconds=e.seconds,
            en=e.en,
            zh=e.zh,
            note=notes_by_seconds.get(e.seconds, e.note),
        )
        for e in transcript
    ]

    return video_brief, key_points, quiz_questions, situation_cards, vocab, annotated
