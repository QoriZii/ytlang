
# Architecture

## Project layout

```
ytlang/
  ├── __init__.py
  ├── config.py              env vars and defaults
  ├── languages.py           language registry and validation
  ├── models.py              LessonData, VocabEntry, TranscriptEntry
  ├── prompts/               LLM prompt templates (per source language)
  │   ├── shared/
  │   │   └── translate.txt  shared translation prompt template
  │   ├── en/                English prompts (preclean, analyze_system, analyze_user)
  │   ├── fr/                French prompts
  │   ├── es/                Spanish prompts
  │   ├── zh/                Chinese prompts
  │   ├── ja/                Japanese prompts
  │   └── ko/                Korean prompts
  ├── pipeline/
  │   ├── fetch.py           YouTube transcript + metadata fetching
  │   ├── preclean.py        LLM-powered ASR cleanup and sentence merging
  │   ├── translate.py       source→native translation (batched, parallelized)
  │   └── analyze.py         vocab, key points, quiz, notes
  ├── render/
  │   ├── render.py          render_all() → 4 HTML files
  │   ├── fragments.py       HTML fragment builders
  │   └── templates/
  │       ├── recording.html
  │       ├── handout.html
  │       ├── transcript.html
  │       ├── quiz.html
  │       └── _partials/     shared CSS/JS snippets
  └── cli/
      └── main.py            typer CLI: prep / render / reprocess / serve
```

## Module details

### `languages.py` — Language Registry

Defines supported languages with name, native name, and YouTube transcript code. Provides `validate_lang()` and `lang_name()` helpers.

### `prompts/` — LLM Prompt Templates

Per-language prompt files loaded by `load_prompts(source_lang, native_lang)`. Each language folder contains:
- `preclean.txt` — ASR cleanup rules (language-specific punctuation)
- `analyze_system.txt` — teacher role prompt
- `analyze_user.txt` — analysis template with `{title}`, `{transcript_text}`, `{native_lang_name}` placeholders

`shared/translate.txt` is used for all language pairs, with `{source_lang_name}` and `{native_lang_name}` placeholders.

### `config.py` — Configuration

Loads from `.env` and environment variables:
- `XAI_API_KEY` — xAI API key
- `XAI_MODEL` — LLM model name
- `OUTPUT_DIR` — where lesson folders are written
- `TEMPLATES_DIR` — HTML template location

### `models.py` — Data Models

| Class | Fields | Purpose |
|-------|--------|---------|
| `VocabEntry` | word, pos, level, pronunciation, definition, example, example_seconds, zh | Single vocabulary item |
| `TranscriptEntry` | seconds, en, zh, note | One transcript line (`en` = source lang, `zh` = native lang) |
| `LessonData` | video_id, title, channel, duration, url, generated_date, source_lang, native_lang, video_brief, key_points, quiz_questions, vocab, transcript | Full lesson — serializes to/from `lesson.json` |

### `pipeline/fetch.py` — YouTube Fetching

| Function | Purpose |
|----------|---------|
| `fetch_video(url, source_lang)` | Main entry — returns (video_id, meta, entries, lang) |
| `fetch_transcript(video_id, lang_pref)` | Fetches via `youtube-transcript-api`, handles errors |
| `_fetch_ytdlp_meta(video_id)` | Rich metadata via `yt-dlp` subprocess |
| `_fetch_html_meta(video_id)` | Fallback: scrapes YouTube page HTML |

### `pipeline/preclean.py` — ASR Cleanup (LLM-powered)

| Function | Purpose |
|----------|---------|
| `preclean(entries, source_lang, native_lang)` | Main entry — restores punctuation, merges into sentences |
| `_preclean_batch(client, fragments, prompt)` | Single API call for one batch |
| `_split_into_batches(fragments)` | Splits at natural pauses (>5s gap), max 80 fragments/batch |

### `pipeline/translate.py` — Translation

| Function | Purpose |
|----------|---------|
| `translate(texts, source_lang, native_lang)` | Main entry — batches of 20, 3 parallel threads |
| `_translate_batch(client, texts, prompt)` | Single API call, returns translated strings |

### `pipeline/analyze.py` — Content Analysis

| Function | Purpose |
|----------|---------|
| `analyze(title, channel, duration, transcript, source_lang, native_lang)` | Single large call → video_brief, key_points, quiz_questions, vocab, annotated transcript |
| `_format_transcript(entries)` | Formats transcript for the prompt |
| `_target_per_level(transcript)` | Calculates vocab count target based on video duration |

### `render/render.py` — HTML Rendering

| Function | Purpose |
|----------|---------|
| `render_all(lesson, outdir)` | Renders all 4 HTML output files |
| `render_recording(lesson, out)` | Embedded YouTube + synced bilingual transcript + vocab cards |
| `render_handout(lesson, out)` | Student worksheet: vocab by level + cloze exercises |
| `render_transcript(lesson, out)` | Bilingual transcript with context notes |
| `render_quiz(lesson, out)` | Interactive MC quiz (vocab + comprehension) |

### `cli/main.py` — CLI Commands

| Command | Purpose |
|---------|---------|
| `prep <url>` | Full pipeline: fetch → preclean → translate → analyze → lesson.json |
| `render [video_id]` | Render lesson.json → 4 HTML files |
| `reprocess [video_id]` | Re-run stages on existing lesson without re-fetching |
| `batch <urls_file>` | Process multiple URLs from a text file |
| `serve [video_id]` | Local HTTP server + auto-open browser |

All commands that run the pipeline accept `--lang` / `-l` (source language) and `--native` / `-n` (native language).

## lesson.json schema

```json
{
  "video_id": "abc123xyz",
  "title": "Video title",
  "channel": "Channel name",
  "duration": "18 min",
  "url": "https://www.youtube.com/watch?v=abc123xyz",
  "generated_date": "2026-05-08",
  "source_lang": "en",
  "native_lang": "zh",
  "video_brief": "2-3 sentences about the video and why it has rich vocabulary.",
  "key_points": [
    { "en": "Key idea in source language", "zh": "Same point in native language" }
  ],
  "quiz_questions": [
    {
      "en": "What does the speaker recommend?",
      "answer": "Use a VPN always",
      "explanation": "At 2:00 the speaker explains...",
      "seconds": 120,
      "difficulty": "easy",
      "distractors": ["Buy antivirus", "Disable firewall", "Use public wifi"]
    }
  ],
  "vocab": [
    {
      "word": "wager",
      "pos": "noun",
      "level": "intermediate",
      "pronunciation": "/ˈwɑːɡər/",
      "definition": "a bet made on an uncertain outcome",
      "example": "You need to wager your coins here.",
      "example_seconds": 45,
      "zh": "打赌"
    }
  ],
  "transcript": [
    {
      "seconds": 45,
      "en": "You need to wager your coins here.",
      "zh": "你需要在这里下注。",
      "note": "Context note in native language."
    }
  ]
}
```

Note: `en` and `zh` field names are kept for backward compatibility. `en` contains the source language text, `zh` contains the native language translation.
