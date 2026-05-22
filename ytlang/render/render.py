"""Render lesson.json data into three HTML files.

All three renderers use simple {{PLACEHOLDER}} substitution on their templates.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from ytlang import config
from ytlang.models import LessonData
from ytlang.languages import lang_name, LANGUAGES
from ytlang.render.fragments import (
    fmt_seconds,
    key_points_html,
    vocab_html,
    cloze_html,
    transcript_lines_html,
)


# ── Template loader ────────────────────────────────────────────────────────────

_PARTIALS_DIR = config.TEMPLATES_DIR / "_partials"


def _load_template(name: str) -> str:
    """Load a template from config.TEMPLATES_DIR."""
    return (config.TEMPLATES_DIR / name).read_text(encoding="utf-8")


def _load_partial(name: str) -> str:
    return (_PARTIALS_DIR / name).read_text(encoding="utf-8")


def _shared_vars(lesson: LessonData) -> dict:
    sl = lesson.source_lang
    nl = lesson.native_lang
    return {
        "LEVEL_COLORS_JS": _load_partial("level_colors.js"),
        "FMT_SECONDS_JS":  _load_partial("fmt_seconds.js"),
        "BACK_BTN_CSS":    _load_partial("back_btn_css.html"),
        "BACK_BTN":        _load_partial("back_btn.html"),
        "SOURCE_LANG_NAME": lang_name(sl),
        "NATIVE_LANG_NAME": LANGUAGES.get(nl, {}).get("native_name", lang_name(nl)),
    }


def _sub(template: str, data: dict) -> str:
    for key, value in data.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template




# ── Individual renderers ───────────────────────────────────────────────────────

def render_recording(lesson: LessonData, out: Path) -> None:
    vocab_sorted = sorted(lesson.vocab, key=lambda v: v.example_seconds)
    transcript_data = [
        {"seconds": e.seconds, "en": e.en, "zh": e.zh}
        for e in lesson.transcript
    ]
    tmpl = _load_template("recording.html")
    result = _sub(tmpl, {**_shared_vars(lesson),
        "VIDEO_ID": lesson.video_id,
        "VIDEO_TITLE": html.escape(lesson.title),
        "META_LINE": f"{html.escape(lesson.channel)} · {html.escape(lesson.duration)}",
        "VOCAB_DATA": json.dumps([v.__dict__ for v in vocab_sorted], ensure_ascii=False),
        "TRANSCRIPT_DATA": json.dumps(transcript_data, ensure_ascii=False),
    })
    out.write_text(result, encoding="utf-8")
    print(f"  recording.html → {out}")


def render_handout(lesson: LessonData, out: Path) -> None:
    by_level = {"basic": [], "intermediate": [], "advanced": []}
    for v in lesson.vocab:
        by_level.setdefault(v.level, []).append(v)

    cloze_exercises, word_bank = cloze_html(lesson.vocab)

    tmpl = _load_template("handout.html")
    result = _sub(tmpl, {**_shared_vars(lesson),
        "VIDEO_TITLE": html.escape(lesson.title),
        "CHANNEL": html.escape(lesson.channel),
        "DURATION": html.escape(lesson.duration),
        "DATE": lesson.generated_date,
        "VIDEO_URL": lesson.url,
        "VIDEO_BRIEF": html.escape(lesson.video_brief),
        "SOURCE_LANG": lesson.source_lang,
        "KEY_POINTS": key_points_html(lesson.key_points),
        "VOCAB_BASIC": vocab_html(by_level.get("basic", [])),
        "VOCAB_INTERMEDIATE": vocab_html(by_level.get("intermediate", [])),
        "VOCAB_ADVANCED": vocab_html(by_level.get("advanced", [])),
        "CLOZE_EXERCISES": cloze_exercises,
        "WORD_BANK": word_bank,
    })
    out.write_text(result, encoding="utf-8")
    print(f"  handout.html   → {out}")


def render_transcript(lesson: LessonData, out: Path) -> None:
    tmpl = _load_template("transcript.html")
    result = _sub(tmpl, {**_shared_vars(lesson),
        "VIDEO_TITLE": html.escape(lesson.title),
        "TRANSCRIPT_LINES": transcript_lines_html(lesson),
    })
    out.write_text(result, encoding="utf-8")
    print(f"  transcript.html → {out}")


def render_quiz(lesson: LessonData, out: Path) -> None:
    vocab_sorted = sorted(lesson.vocab, key=lambda v: v.example_seconds)
    tmpl = _load_template("quiz.html")
    result = _sub(tmpl, {**_shared_vars(lesson),
        "VIDEO_TITLE": html.escape(lesson.title),
        "VOCAB_DATA": json.dumps([v.__dict__ for v in vocab_sorted], ensure_ascii=False),
        "QUIZ_QUESTIONS_DATA": json.dumps(lesson.quiz_questions, ensure_ascii=False),
        "SITUATION_CARDS_DATA": json.dumps(lesson.situation_cards, ensure_ascii=False),
        "VIDEO_URL": json.dumps(lesson.url),
    })
    out.write_text(result, encoding="utf-8")
    print(f"  quiz.html      → {out}")


# ── Combined ───────────────────────────────────────────────────────────────────

def render_all(lesson: LessonData, outdir: Path) -> None:
    """Render recording.html, handout.html, transcript.html, quiz.html into outdir."""
    outdir.mkdir(parents=True, exist_ok=True)
    render_recording(lesson, outdir / "recording.html")
    render_handout(lesson, outdir / "handout.html")
    render_transcript(lesson, outdir / "transcript.html")
    render_quiz(lesson, outdir / "quiz.html")
