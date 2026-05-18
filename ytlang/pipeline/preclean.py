"""Clean and merge raw YouTube auto-caption fragments via Grok.

Takes raw ASR fragments (seconds + text), restores punctuation and
capitalization, merges fragments into sentence-level chunks, and returns
TranscriptEntry objects ready for translation.
"""
from __future__ import annotations

import json
import re
from typing import List

from ytlang import config
from ytlang.models import TranscriptEntry
from ytlang.pipeline.fetch import RawTranscriptEntry
from ytlang.pipeline.utils import make_client, parse_llm_json
from ytlang.languages import DEFAULT_SOURCE_LANG, DEFAULT_NATIVE_LANG

GAP_THRESHOLD = 5      # seconds — split into batches at pauses longer than this
MAX_SINGLE_FRAGMENTS = 80   # use batching above this fragment count

_SENTENCE_END_RE = re.compile(r'(?<![A-Z\d])\.(?![A-Za-z\d])["\']?|[?!]["\']?')
_MIN_RETRY_BATCH = 10   # don't split below this size


def _is_collapsed(entry: TranscriptEntry) -> bool:
    """Return True if an entry appears to contain multiple sentences."""
    return len(_SENTENCE_END_RE.findall(entry.en)) >= 3


def _preclean_batch(client, fragments: List[dict], preclean_prompt: str) -> List[TranscriptEntry]:
    from xai_sdk.chat import system, user

    chat = client.chat.create(model=config.XAI_MODEL, max_tokens=32768)
    chat.append(system(preclean_prompt))
    chat.append(user(json.dumps(fragments, ensure_ascii=False)))

    response = chat.sample()
    data = parse_llm_json(response.content)
    return [
        TranscriptEntry(seconds=int(e["seconds"]), en=e["en"], zh="", note="")
        for e in data
    ]


def _split_into_batches(fragments: List[dict]) -> List[List[dict]]:
    """Split fragments into batches of MAX_SINGLE_FRAGMENTS, preferring gap boundaries."""
    if not fragments:
        return []
    batches: List[List[dict]] = []
    start = 0
    while start < len(fragments):
        end = min(start + MAX_SINGLE_FRAGMENTS, len(fragments))
        # If not at the end, try to extend to the next gap boundary (up to 20 more)
        if end < len(fragments):
            for lookahead in range(end, min(end + 20, len(fragments))):
                if fragments[lookahead]["seconds"] - fragments[lookahead - 1]["seconds"] > GAP_THRESHOLD:
                    end = lookahead
                    break
        batches.append(fragments[start:end])
        start = end
    return batches


def preclean(entries: List[RawTranscriptEntry], source_lang: str = DEFAULT_SOURCE_LANG, native_lang: str = DEFAULT_NATIVE_LANG) -> List[TranscriptEntry]:
    """Clean and merge raw caption fragments into sentence-level TranscriptEntry objects.

    Uses a single LLM call for short transcripts. For longer ones (> MAX_SINGLE_FRAGMENTS
    fragments), splits at natural pause gaps and processes each batch separately.
    Falls back to the original fragments if a batch fails.
    """
    if not entries:
        return []

    if not config.XAI_API_KEY:
        raise ValueError("XAI_API_KEY is not set. Export it: export XAI_API_KEY=xai-...")

    from ytlang.prompts import load_prompts
    prompts = load_prompts(source_lang, native_lang)
    preclean_prompt = prompts["preclean"]

    client = make_client()
    fragments = [{"seconds": e.seconds, "text": e.text} for e in entries]

    def _run_batch(batch: List[dict], label: str, depth: int = 0) -> List[TranscriptEntry]:
        try:
            result = _preclean_batch(client, batch, preclean_prompt)
        except Exception as exc:
            print(f"[preclean] Warning: {label} failed ({exc}); using original")
            return [TranscriptEntry(seconds=f["seconds"], en=f["text"], zh="", note="") for f in batch]
        if not result:
            print(f"[preclean] Warning: {label} returned empty result; using original")
            return [TranscriptEntry(seconds=f["seconds"], en=f["text"], zh="", note="") for f in batch]

        collapsed = [e for e in result if _is_collapsed(e)]
        if collapsed and depth < 3 and len(batch) > _MIN_RETRY_BATCH:
            mid = len(batch) // 2
            print(f"[preclean] {len(collapsed)} collapsed entry/entries in {label} ({len(batch)} fragments), retrying as {mid}+{len(batch)-mid}")
            return (
                _run_batch(batch[:mid], f"{label}a", depth + 1)
                + _run_batch(batch[mid:], f"{label}b", depth + 1)
            )

        return result

    if len(fragments) <= MAX_SINGLE_FRAGMENTS:
        return _run_batch(fragments, "preclean")

    # Long transcript: split into fixed-size batches (preferring gap boundaries)
    batches = _split_into_batches(fragments)
    print(f"[preclean] Long transcript ({len(fragments)} fragments) → {len(batches)} batches")
    results: List[TranscriptEntry] = []
    for i, batch in enumerate(batches):
        results.extend(_run_batch(batch, f"batch {i + 1}/{len(batches)}"))
    return results
