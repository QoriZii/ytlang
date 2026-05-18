"""Load language-specific prompt templates."""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompts(source_lang: str, native_lang: str) -> dict[str, str]:
    """Load prompt templates for a given source/native language pair.

    Returns dict with keys: preclean, translate, analyze_system, analyze_user.
    The analyze_user value is a template string with {title}, {channel}, etc. placeholders.
    """
    from ytlang.languages import lang_name

    lang_dir = PROMPTS_DIR / source_lang
    shared_dir = PROMPTS_DIR / "shared"

    if not lang_dir.exists():
        raise ValueError(f"No prompts for source language: {source_lang}")

    context = {
        "source_lang_name": lang_name(source_lang),
        "native_lang_name": lang_name(native_lang),
    }

    return {
        "preclean": (lang_dir / "preclean.txt").read_text().format(**context),
        "translate": (shared_dir / "translate.txt").read_text().format(**context),
        "analyze_system": (lang_dir / "analyze_system.txt").read_text().format(**context),
        "analyze_user": (lang_dir / "analyze_user.txt").read_text(),
    }
