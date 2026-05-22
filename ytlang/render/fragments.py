"""HTML fragment builders for lesson rendering."""
from __future__ import annotations

import html
import re

from ytlang.models import LessonData, VocabEntry


def fmt_seconds(s: int) -> str:
    m, sec = divmod(s, 60)
    return f"{m}:{sec:02d}"



def key_points_html(key_points: list[dict]) -> str:
    items = []
    for kp in key_points:
        en_text = kp.get("en", "")
        zh_text = kp.get("zh", "")
        zh_span = f'<span class="kp-zh" lang="zh">{html.escape(zh_text)}</span>' if zh_text else ""
        items.append(
            f'<li class="kp-entry">'
            f'<span class="kp-en">{html.escape(en_text)}</span>'
            f'{zh_span}'
            f"</li>"
        )
    return "\n".join(items)


def vocab_html(vocab: list[VocabEntry]) -> str:
    items = []
    for v in vocab:
        pron_html = f'<span class="pron">{html.escape(v.pronunciation)}</span>' if v.pronunciation else ""
        items.append(
            f'<li class="vocab-entry">'
            f'<div class="entry-head">'
            f'<span class="word">{html.escape(v.word)}</span>'
            f'<button class="speak-btn" data-word="{html.escape(v.word, quote=True)}" title="Listen">'
            f'<span class="material-symbols-outlined">volume_up</span></button>'
            f'<span class="pos">{html.escape(v.pos)}</span>'
            f'<span class="zh" lang="zh">{html.escape(v.zh)}</span>'
            f"</div>"
            f'{pron_html}'
            f'<p class="def">{html.escape(v.definition)}</p>'
            f'<p class="ex">"{html.escape(v.example)}"</p>'
            f"</li>"
        )
    return "\n".join(items)


def cloze_html(vocab: list[VocabEntry]) -> tuple[str, str]:
    """Return (exercises_html, word_bank_html) for fill-in-the-blank section."""
    if not vocab:
        return "", ""

    blank = '<span class="cloze-blank"></span>'
    items = []

    for v in sorted(vocab, key=lambda x: x.example_seconds):
        escaped = html.escape(v.example)
        word_esc = html.escape(v.word)
        pattern = re.compile(rf'\b{re.escape(word_esc)}\b', re.IGNORECASE)
        sentence_html, n = pattern.subn(blank, escaped, count=1)
        if n == 0:
            idx = escaped.lower().find(word_esc.lower())
            if idx >= 0:
                sentence_html = escaped[:idx] + blank + escaped[idx + len(word_esc):]
            else:
                sentence_html = escaped + ' ' + blank
        ts = fmt_seconds(v.example_seconds)
        items.append(
            f'<li class="cloze-entry">'
            f'<span class="cloze-ts">[{ts}]</span> '
            f'<span class="cloze-sentence">{sentence_html}</span>'
            f'</li>'
        )

    bank_words = sorted({v.word for v in vocab})
    word_bank_html = ' &nbsp;·&nbsp; '.join(
        f'<span class="bank-word">{html.escape(w)}</span>' for w in bank_words
    )
    return '\n'.join(items), word_bank_html


def transcript_lines_html(lesson: LessonData) -> str:
    parts = []
    for e in lesson.transcript:
        ts = fmt_seconds(e.seconds)
        source_line = f'<span class="en">{html.escape(e.en)}</span>'
        native_line = f'<span class="zh">{html.escape(e.zh)}</span>'
        if e.note:
            parts.append(
                f'<div class="line has-note">'
                f'<span class="ts">{ts}</span>'
                f'<div class="text-block">'
                f'{source_line}'
                f'{native_line}'
                f'<div class="note">{html.escape(e.note)}</div>'
                f"</div>"
                f"</div>"
            )
        else:
            parts.append(
                f'<div class="line">'
                f'<span class="ts">{ts}</span>'
                f'<div class="text-block">{source_line}{native_line}</div>'
                f"</div>"
            )
    return "\n".join(parts)
