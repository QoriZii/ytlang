"""yt-en-class CLI

Commands:
  prep  <url>            Fetch, translate, analyze → write lesson.json
  render [video_id]      Render lesson.json → 3 HTML files
  batch <urls_file>      Run prep (and optionally render) for a list of URLs
  serve [video_id]       Serve lesson output over HTTP and open in browser
"""
from __future__ import annotations

import datetime
import functools
import http.server
import json
import socket
import socketserver
import sys
import webbrowser
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Optional

import typer

from ytlang import config
from ytlang.models import LessonData, TranscriptEntry
from ytlang.pipeline.utils import parse_video_id
from ytlang.languages import DEFAULT_SOURCE_LANG, DEFAULT_NATIVE_LANG, validate_lang

def _version_callback(value: bool):
    if value:
        typer.echo(f"ytlang {pkg_version('ytlang')} — by QoriZii (https://github.com/QoriZii/ytlang)")
        raise typer.Exit()

app = typer.Typer(help="Generate language lesson materials from YouTube videos.")

@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit"),
):
    pass


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _outdir(video_id: str, base: Optional[Path] = None) -> Path:
    return (base or config.OUTPUT_DIR) / video_id


def _latest_video_id(base: Optional[Path] = None) -> Optional[str]:
    """Return the most recently modified video_id directory."""
    root = base or config.OUTPUT_DIR
    if not root.exists():
        return None
    dirs = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for d in dirs:
        if d.is_dir() and (d / "lesson.json").exists():
            return d.name
    return None



# ── prep ───────────────────────────────────────────────────────────────────────

def _run_prep(url: str, outdir_base: Optional[Path] = None, source_lang: str = DEFAULT_SOURCE_LANG, native_lang: str = DEFAULT_NATIVE_LANG) -> Optional[Path]:
    """Run the full prep pipeline for one URL. Returns lesson.json path, or None on error."""
    from ytlang.pipeline.fetch import fetch_video
    from ytlang.pipeline.preclean import preclean
    from ytlang.pipeline.translate import translate
    from ytlang.pipeline.analyze import analyze

    typer.echo(f"  Fetching transcript…")
    try:
        video_id, meta, raw_entries, transcript_lang = fetch_video(url, source_lang=source_lang)
    except RuntimeError as e:
        typer.echo(f"  Error: {e}", err=True)
        return None
    except ImportError as e:
        typer.echo(f"  Missing dependency: {e}", err=True)
        raise typer.Exit(1)

    out = _outdir(video_id, outdir_base)
    raw_path = out / "raw.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        json.dumps([{"seconds": e.seconds, "text": e.text} for e in raw_entries], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    typer.echo(f"  Cleaning and merging {len(raw_entries)} segments…")
    transcript = preclean(raw_entries, source_lang=source_lang, native_lang=native_lang)

    typer.echo(f"  Translating {len(transcript)} segments…")
    zh_texts = translate([e.en for e in transcript], source_lang=source_lang, native_lang=native_lang)
    transcript = [
        TranscriptEntry(seconds=e.seconds, en=e.en, zh=zh)
        for e, zh in zip(transcript, zh_texts)
    ]

    typer.echo(f"  Analyzing with {config.XAI_MODEL}…")
    try:
        video_brief, key_points, quiz_questions, vocab, transcript = analyze(
            title=meta.title,
            channel=meta.channel,
            duration=meta.duration,
            transcript=transcript,
            source_lang=source_lang,
            native_lang=native_lang,
        )
    except ValueError as e:
        typer.echo(f"  Error: {e}", err=True)
        raise typer.Exit(1)

    lesson = LessonData(
        video_id=video_id,
        title=meta.title,
        channel=meta.channel,
        duration=meta.duration,
        url=f"https://www.youtube.com/watch?v={video_id}",
        generated_date=datetime.date.today().isoformat(),
        video_brief=video_brief,
        source_lang=source_lang,
        native_lang=native_lang,
        key_points=key_points,
        quiz_questions=quiz_questions,
        vocab=vocab,
        transcript=transcript,
    )

    lesson_path = out / "lesson.json"
    lesson.save(lesson_path)

    basic = sum(1 for v in vocab if v.level == "basic")
    intermediate = sum(1 for v in vocab if v.level == "intermediate")
    advanced = sum(1 for v in vocab if v.level == "advanced")
    typer.echo(f"  lesson.json → {lesson_path}")
    typer.echo(f"  Vocab: Basic {basic} · Intermediate {intermediate} · Advanced {advanced}")
    return lesson_path


@app.command()
def prep(
    url: str = typer.Argument(..., help="YouTube video URL"),
    outdir: Optional[Path] = typer.Option(None, "--outdir", "-o", help="Override output directory"),
    lang: str = typer.Option(DEFAULT_SOURCE_LANG, "--lang", "-l", help="Source language to learn (en/fr/es)"),
    native: str = typer.Option(DEFAULT_NATIVE_LANG, "--native", "-n", help="Learner's native language (zh/ko/ja/en)"),
    render: bool = typer.Option(False, "--render", "-r", help="Also render HTML after prep"),
):
    """Fetch, translate, and analyze a YouTube video. Writes lesson.json."""
    validate_lang(lang)
    validate_lang(native)
    typer.echo(f"Prepping: {url} (source={lang}, native={native})")
    lesson_path = _run_prep(url, outdir, source_lang=lang, native_lang=native)
    if lesson_path and render:
        _run_render(lesson_path.parent.name, outdir)


# ── render ─────────────────────────────────────────────────────────────────────

def _run_render(video_id: str, outdir_base: Optional[Path] = None, open_browser: bool = False) -> None:
    from ytlang.render.render import render_all

    out = _outdir(video_id, outdir_base)
    lesson_path = out / "lesson.json"
    if not lesson_path.exists():
        typer.echo(f"Error: {lesson_path} not found. Run `prep` first.", err=True)
        raise typer.Exit(1)

    lesson = LessonData.load(lesson_path)
    typer.echo(f"Rendering: {lesson.title}")
    render_all(lesson, out)

    if open_browser:
        recording = out / "recording.html"
        webbrowser.open(recording.as_uri())


@app.command()
def render(
    video_id: Optional[str] = typer.Argument(None, help="Video ID (defaults to most recent)"),
    outdir: Optional[Path] = typer.Option(None, "--outdir", "-o", help="Override output directory"),
    open_: bool = typer.Option(False, "--open", help="Open recording.html in browser after render"),
):
    """Render lesson.json into recording.html, handout.html, transcript.html."""
    vid = video_id or _latest_video_id(outdir)
    if not vid:
        typer.echo("Error: no video_id given and no processed lessons found.", err=True)
        raise typer.Exit(1)
    _run_render(vid, outdir, open_browser=open_)


# ── reprocess ──────────────────────────────────────────────────────────────────

def _run_reprocess(
    video_id: str,
    outdir_base: Optional[Path],
    do_translate: bool,
    do_analyze: bool,
    from_preclean: bool = False,
    source_lang: Optional[str] = None,
    native_lang: Optional[str] = None,
) -> None:
    from ytlang.pipeline.translate import translate
    from ytlang.pipeline.analyze import analyze

    out = _outdir(video_id, outdir_base)
    lesson_path = out / "lesson.json"
    if not lesson_path.exists():
        typer.echo(f"Error: {lesson_path} not found. Run `prep` first.", err=True)
        raise typer.Exit(1)

    lesson = LessonData.load(lesson_path)
    # Use CLI overrides if given, otherwise use what's stored in lesson.json
    sl = source_lang or lesson.source_lang
    nl = native_lang or lesson.native_lang
    lesson.source_lang = sl
    lesson.native_lang = nl
    typer.echo(f"Reprocessing: {lesson.title} (source={sl}, native={nl})")

    if from_preclean:
        from ytlang.pipeline.preclean import preclean
        from ytlang.pipeline.fetch import RawTranscriptEntry

        raw_path = out / "raw.json"
        if not raw_path.exists():
            typer.echo(f"Error: {raw_path} not found. Re-run `prep` to generate it.", err=True)
            raise typer.Exit(1)

        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        raw_entries = [RawTranscriptEntry(seconds=e["seconds"], text=e["text"]) for e in raw]
        typer.echo(f"  Cleaning and merging {len(raw_entries)} segments…")
        lesson.transcript = preclean(raw_entries, source_lang=sl, native_lang=nl)

    if do_translate:
        typer.echo(f"  Translating {len(lesson.transcript)} segments…")
        zh_texts = translate([e.en for e in lesson.transcript], source_lang=sl, native_lang=nl)
        lesson.transcript = [
            TranscriptEntry(seconds=e.seconds, en=e.en, zh=zh, note=e.note)
            for e, zh in zip(lesson.transcript, zh_texts)
        ]

    if do_analyze:
        typer.echo(f"  Analyzing with {config.XAI_MODEL}…")
        video_brief, key_points, quiz_questions, vocab, annotated = analyze(
            title=lesson.title,
            channel=lesson.channel,
            duration=lesson.duration,
            transcript=lesson.transcript,
            source_lang=sl,
            native_lang=nl,
        )
        lesson.video_brief = video_brief
        lesson.key_points = key_points
        lesson.quiz_questions = quiz_questions
        lesson.vocab = vocab
        lesson.transcript = annotated

    lesson.generated_date = datetime.date.today().isoformat()
    lesson.save(lesson_path)
    typer.echo(f"  lesson.json → {lesson_path}")


@app.command()
def reprocess(
    video_id: Optional[str] = typer.Argument(None, help="Video ID (defaults to most recent)"),
    outdir: Optional[Path] = typer.Option(None, "--outdir", "-o", help="Override output directory"),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="Override source language (en/fr/es)"),
    native: Optional[str] = typer.Option(None, "--native", "-n", help="Override native language (zh/ko/ja/en)"),
    from_preclean: bool = typer.Option(False, "--from-preclean/--no-from-preclean", help="Re-run from preclean+merge using saved raw.json"),
    do_translate: bool = typer.Option(True, "--translate/--no-translate", help="Re-run translation"),
    do_analyze: bool = typer.Option(True, "--analyze/--no-analyze", help="Re-run analysis"),
    render: bool = typer.Option(False, "--render", "-r", help="Also re-render HTML after reprocessing"),
):
    """Re-run pipeline stages on an existing lesson without re-fetching from YouTube."""
    if lang:
        validate_lang(lang)
    if native:
        validate_lang(native)
    vid = video_id or _latest_video_id(outdir)
    if not vid:
        typer.echo("Error: no video_id given and no processed lessons found.", err=True)
        raise typer.Exit(1)
    _run_reprocess(vid, outdir, do_translate, do_analyze, from_preclean, source_lang=lang, native_lang=native)
    if render:
        _run_render(vid, outdir)


# ── batch ──────────────────────────────────────────────────────────────────────

# @app.command()
# def batch(
#     urls_file: Path = typer.Argument(..., help="Text file with one YouTube URL per line"),
#     outdir: Optional[Path] = typer.Option(None, "--outdir", "-o", help="Override output directory"),
#     lang: str = typer.Option(DEFAULT_SOURCE_LANG, "--lang", "-l", help="Source language to learn (en/fr/es)"),
#     native: str = typer.Option(DEFAULT_NATIVE_LANG, "--native", "-n", help="Learner's native language (zh/ko/ja/en)"),
#     render: bool = typer.Option(False, "--render", "-r", help="Render HTML after each prep"),
#     skip_existing: bool = typer.Option(True, "--skip-existing/--no-skip", help="Skip videos already processed"),
# ):
#     """Batch prep (and optionally render) a list of YouTube URLs."""
#     validate_lang(lang)
#     validate_lang(native)
#     if not urls_file.exists():
#         typer.echo(f"Error: {urls_file} not found.", err=True)
#         raise typer.Exit(1)

#     lines = urls_file.read_text().splitlines()
#     urls = [
#         l.strip() for l in lines
#         if l.strip() and not l.strip().startswith("#")
#     ]

#     if not urls:
#         typer.echo("No URLs found in file.")
#         return

#     typer.echo(f"Batch: {len(urls)} URL(s) from {urls_file}")

#     done, skipped, failed = 0, 0, 0

#     for i, url in enumerate(urls, 1):
#         typer.echo(f"\n[{i}/{len(urls)}] {url}")

#         if skip_existing:
#             try:
#                 video_id = parse_video_id(url)
#                 lesson_path = _outdir(video_id, outdir) / "lesson.json"
#                 if lesson_path.exists():
#                     typer.echo("  Skipped (lesson.json already exists)")
#                     skipped += 1
#                     continue
#             except Exception:
#                 pass

#         lesson_path = _run_prep(url, outdir, source_lang=lang, native_lang=native)
#         if lesson_path is None:
#             failed += 1
#             continue

#         if render:
#             try:
#                 _run_render(lesson_path.parent.name, outdir)
#             except Exception as e:
#                 typer.echo(f"  Render error: {e}", err=True)

#         done += 1

#     typer.echo(f"\nBatch complete: {done} done · {skipped} skipped · {failed} failed")


# ── serve ──────────────────────────────────────────────────────────────────────

def _find_free_port(start: int = 8765, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"No free port found in range {start}–{start + attempts - 1}")


@app.command()
def serve(
    video_id: Optional[str] = typer.Argument(None, help="Video ID (defaults to most recent)"),
    outdir: Optional[Path] = typer.Option(None, "--outdir", "-o", help="Override output directory"),
    port: int = typer.Option(0, "--port", "-p", help="Port to listen on (0 = auto-select from 8765)"),
):
    """Serve lesson HTML over HTTP and open recording.html in the browser."""
    vid = video_id or _latest_video_id(outdir)
    if not vid:
        typer.echo("Error: no video_id given and no processed lessons found.", err=True)
        raise typer.Exit(1)

    lesson_dir = _outdir(vid, outdir)
    if not (lesson_dir / "recording.html").exists():
        typer.echo(f"Error: recording.html not found in {lesson_dir}. Run `render` first.", err=True)
        raise typer.Exit(1)

    root = lesson_dir.parent
    actual_port = port if port else _find_free_port()

    class _Server(socketserver.TCPServer):
        allow_reuse_address = True

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)
        def log_message(self, *args):
            pass

    server = _Server(("127.0.0.1", actual_port), _Handler)

    url = f"http://localhost:{actual_port}/{vid}/recording.html"
    typer.echo(f"Serving {root}")
    typer.echo(f"  → {url}")
    typer.echo("Press Ctrl+C to stop.")

    webbrowser.open_new_tab(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        typer.echo("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    app()
