"""Language registry for multi-language support."""

from __future__ import annotations

LANGUAGES = {
    "en": {
        "name": "English",
        "native_name": "英语",
        "transcript_code": "en",
    },
    "fr": {
        "name": "French",
        "native_name": "法语",
        "transcript_code": "fr",
    },
    "es": {
        "name": "Spanish",
        "native_name": "西班牙语",
        "transcript_code": "es",
    },
    "zh": {
        "name": "Chinese (Simplified)",
        "native_name": "中文",
        "transcript_code": "zh-Hans",
    },
    "ko": {
        "name": "Korean",
        "native_name": "한국어",
        "transcript_code": "ko",
    },
    "ja": {
        "name": "Japanese",
        "native_name": "日语",
        "transcript_code": "ja",
    },
}

DEFAULT_SOURCE_LANG = "en"
DEFAULT_NATIVE_LANG = "zh"


def lang_name(code: str) -> str:
    return LANGUAGES[code]["name"]


def validate_lang(code: str) -> None:
    if code not in LANGUAGES:
        supported = ", ".join(sorted(LANGUAGES))
        raise ValueError(f"Unsupported language '{code}'. Supported: {supported}")
