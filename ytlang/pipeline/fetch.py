"""Fetch YouTube transcript and metadata.

Absorbs logic from video-lens/scripts/fetch_transcript.py and fetch_metadata.py.
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from typing import List

from ytlang.pipeline.utils import parse_video_id


# ── Data types ─────────────────────────────────────────────────────────────────

@dataclass
class RawTranscriptEntry:
    seconds: int
    text: str


@dataclass
class VideoMeta:
    title: str
    channel: str
    duration: str       # e.g. "12 min" or "1h 4m"
    published: str      # e.g. "Jan 5 2024"
    views: str          # e.g. "1.2M views"
    description: str    # plain text, may be empty


# ── Helpers ────────────────────────────────────────────────────────────────────



def _format_duration(total_s: int) -> str:
    h, rem = divmod(total_s, 3600)
    m = rem // 60
    return f"{h}h {m}m" if h > 0 else f"{m} min"


def _format_views(v: int) -> str:
    if v >= 1_000_000:
        return f"{v / 1e6:.1f}M views"
    if v >= 1_000:
        return f"{v / 1e3:.0f}K views"
    return f"{v} views"


def _format_published_yt(date8: str) -> str:
    """YYYYMMDD → 'Jan 5 2024'"""
    if len(date8) != 8:
        return ""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{months[int(date8[4:6]) - 1]} {int(date8[6:8])} {date8[:4]}"


# ── HTML-based metadata fallback ───────────────────────────────────────────────

def _fetch_html_meta(video_id: str) -> VideoMeta:
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")

        title = ""
        m = re.search(r"<title>([^<]+)</title>", html)
        if m:
            title = m.group(1).replace(" - YouTube", "").strip()

        channel = ""
        m = re.search(r'"channelName"\s*:\s*"([^"]+)"', html)
        if m:
            channel = m.group(1)

        published = ""
        m = re.search(r'"publishDate"\s*:\s*"([^"]+)"', html)
        if m:
            parts = m.group(1)[:10].split("-")
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            published = f"{months[int(parts[1]) - 1]} {int(parts[2])} {parts[0]}"

        views = ""
        m = re.search(r'"viewCount"\s*:\s*"([0-9]+)"', html)
        if m:
            views = _format_views(int(m.group(1)))

        duration = ""
        m = re.search(r'"lengthSeconds"\s*:\s*"([0-9]+)"', html)
        if m:
            duration = _format_duration(int(m.group(1)))

        print("  Metadata source: HTML scrape")
        return VideoMeta(title=title, channel=channel, duration=duration,
                         published=published, views=views, description="")
    except Exception:
        return VideoMeta(title="", channel="", duration="", published="", views="", description="")


# ── yt-dlp metadata (richer, optional) ────────────────────────────────────────

def _fetch_ytdlp_meta(video_id: str) -> VideoMeta | None:
    """Returns enriched metadata via yt-dlp, or None if yt-dlp is unavailable."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        result = subprocess.run(
            ["yt-dlp", "--skip-download", "--quiet", "--no-warnings",
             "--no-check-formats", "--dump-json", url],
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None

    if not result.stdout.strip():
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    print("  Metadata source: yt-dlp")
    return VideoMeta(
        title=data.get("title") or "",
        channel=data.get("channel") or "",
        duration=_format_duration(int(data.get("duration") or 0)),
        published=_format_published_yt(data.get("upload_date") or ""),
        views=_format_views(int(data.get("view_count") or 0)),
        description=(data.get("description") or "")[:3000],
    )


# ── Transcript fetch ───────────────────────────────────────────────────────────

def fetch_transcript(video_id: str, lang_pref: str = "en") -> tuple[List[RawTranscriptEntry], str]:
    """Fetch transcript from YouTube. Returns list of (seconds, text) entries.

    Raises:
        ImportError: if youtube-transcript-api is not installed
        RuntimeError: if transcript cannot be fetched (with error code in message)
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise ImportError("pip install 'youtube-transcript-api>=0.6.3'")

    # Defensive imports for exception classes
    def _import_exc(*names):
        from youtube_transcript_api import __dict__ as _d
        return tuple(_d.get(n) for n in names)

    (TranscriptsDisabled, VideoUnavailable, NoTranscriptFound, InvalidVideoId,
     AgeRestricted, IpBlocked, RequestBlocked, PoTokenRequired,
     YouTubeRequestFailed) = _import_exc(
        "TranscriptsDisabled", "VideoUnavailable", "NoTranscriptFound", "InvalidVideoId",
        "AgeRestricted", "IpBlocked", "RequestBlocked", "PoTokenRequired",
        "YouTubeRequestFailed",
    )

    error_map = [
        (TranscriptsDisabled,  "CAPTIONS_DISABLED"),
        (AgeRestricted,        "AGE_RESTRICTED"),
        (VideoUnavailable,     "VIDEO_UNAVAILABLE"),
        (InvalidVideoId,       "INVALID_VIDEO_ID"),
        (IpBlocked,            "IP_BLOCKED"),
        (RequestBlocked,       "REQUEST_BLOCKED"),
        (PoTokenRequired,      "PO_TOKEN_REQUIRED"),
        (NoTranscriptFound,    "NO_TRANSCRIPT"),
        (YouTubeRequestFailed, "NETWORK_ERROR"),
    ]

    try:
        try:
            tlist = YouTubeTranscriptApi().list(video_id)
        except (AttributeError, TypeError):
            tlist = YouTubeTranscriptApi.list_transcripts(video_id)
    except Exception as e:
        code = "TRANSCRIPT_FETCH_FAILED"
        for cls, mapped in error_map:
            if cls is not None and isinstance(e, cls):
                code = mapped
                break
        raise RuntimeError(f"{code}: {e}") from e

    # Language selection: native exact → any exact → native fallback → first
    candidates = list(tlist)
    is_native = lambda t: not getattr(t, "is_translation", False)

    transcript_obj = (
        next((t for t in candidates if t.language_code == lang_pref and is_native(t)), None)
        or next((t for t in candidates if t.language_code == lang_pref), None)
        or next((t for t in candidates if is_native(t)), None)
        or candidates[0]
    )

    raw = transcript_obj.fetch()
    use_dict = isinstance(raw[0], dict) if raw else False

    entries = []
    for s in raw:
        text = s["text"] if use_dict else s.text
        start = s["start"] if use_dict else s.start
        entries.append(RawTranscriptEntry(seconds=int(start), text=text.strip()))

    return entries, transcript_obj.language_code


# ── Combined fetch ─────────────────────────────────────────────────────────────

def fetch_video(url: str, source_lang: str = "en") -> tuple[str, VideoMeta, List[RawTranscriptEntry], str]:
    """Main entry point. Returns (video_id, meta, transcript_entries, transcript_lang).

    Tries yt-dlp for metadata; falls back to HTML scrape.
    """
    from ytlang.languages import LANGUAGES
    video_id = parse_video_id(url)
    meta = _fetch_ytdlp_meta(video_id) or _fetch_html_meta(video_id)
    transcript_code = LANGUAGES.get(source_lang, {}).get("transcript_code", source_lang)
    transcript, lang = fetch_transcript(video_id, lang_pref=transcript_code)
    return video_id, meta, transcript, lang
