from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class VocabEntry:
    word: str
    pos: str                  # noun | verb | adj | adv | phrase
    level: str                # basic | intermediate | advanced
    definition: str
    example: str              # exact quote from transcript
    example_seconds: int
    zh: str                   # Chinese translation
    pronunciation: str = ""   # IPA or phonetic spelling

    @staticmethod
    def from_dict(d: dict) -> "VocabEntry":
        return VocabEntry(
            word=d["word"],
            pos=d.get("pos", ""),
            level=d.get("level", "basic"),
            definition=d.get("definition", ""),
            example=d.get("example", ""),
            example_seconds=int(d.get("example_seconds", 0)),
            zh=d.get("zh", ""),
            pronunciation=d.get("pronunciation", ""),
        )


@dataclass
class TranscriptEntry:
    seconds: int
    en: str
    zh: str
    note: str = ""

    @staticmethod
    def from_dict(d: dict) -> "TranscriptEntry":
        return TranscriptEntry(
            seconds=int(d["seconds"]),
            en=d["en"],
            zh=d["zh"],
            note=d.get("note", ""),
        )


@dataclass
class LessonData:
    video_id: str
    title: str
    channel: str
    duration: str
    url: str
    generated_date: str
    video_brief: str
    source_lang: str = "en"
    native_lang: str = "zh"
    key_points: List[Dict[str, Any]] = field(default_factory=list)
    quiz_questions: List[Dict[str, Any]] = field(default_factory=list)
    vocab: List[VocabEntry] = field(default_factory=list)
    transcript: List[TranscriptEntry] = field(default_factory=list)

    # ── Serialisation ──────────────────────────────────────────────

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))

    @staticmethod
    def load(path: Path) -> "LessonData":
        raw = json.loads(path.read_text())
        return LessonData(
            video_id=raw["video_id"],
            title=raw["title"],
            channel=raw["channel"],
            duration=raw["duration"],
            url=raw["url"],
            generated_date=raw["generated_date"],
            video_brief=raw.get("video_brief", raw.get("game_intro", "")),
            source_lang=raw.get("source_lang", "en"),
            native_lang=raw.get("native_lang", "zh"),
            key_points=raw.get("key_points", []),
            quiz_questions=raw.get("quiz_questions", []),
            vocab=[VocabEntry.from_dict(v) for v in raw.get("vocab", [])],
            transcript=[TranscriptEntry.from_dict(t) for t in raw.get("transcript", [])],
        )
