"""CLI entry point for derush tool."""

import logging
from pathlib import Path

import typer

from derush import __version__
from derush.config import CutterConfig
from derush.cutter import run_pipeline
from derush.exceptions import DerushError, ExportError, MediaInfoError, TranscriptionError
from derush.exporters import JSONExporter, get_fcpxml_exporter
from derush.media_info import get_media_info
from derush.transcriber import transcribe

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for application.

    Args:
        verbose: If True, set level to DEBUG, otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(
    input_file: Path = typer.Argument(
        ..., exists=True, help="Input video or audio file (mp4, mov, mkv, wav, mp3)"
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: next to input file, same stem with .fcpxml or .json)",
    ),
    output_format: str = typer.Option(
        "fcpxml", "--format", "-f", help="Output format: fcpxml or json"
    ),
    language: str | None = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language code (fr, en). Auto-detected from transcription if not specified.",
    ),
    min_silence: float = typer.Option(
        0.5, "--min-silence", help="Minimum silence duration in seconds to cut"
    ),
    min_gap: float = typer.Option(
        0.3,
        "--min-gap",
        help="Minimum gap between words to cut (smaller gaps are kept for natural flow)",
    ),
    cut_padding: float = typer.Option(
        0.0,
        "--cut-padding",
        help="Seconds to keep at each side of cuts for smoother transitions (0-1s; cuts too short are left unchanged)",
    ),
    fillers: str | None = typer.Option(
        None, "--fillers", help="Custom filler words (comma-separated)"
    ),
    fps: float | None = typer.Option(
        None, "--fps", help="Override FPS (auto-detected from video by default)"
    ),
    model: str = typer.Option(
        "base", "--model", "-m", help="Whisper model size: tiny, base, small, medium, large"
    ),
    device: str = typer.Option("cpu", "--device", help="Device for transcription: cpu or cuda"),
    chunk_size: int = typer.Option(
        15,
        "--chunk-size",
        help="Max VAD chunk size in seconds (smaller = more segments, better filler detection)",
    ),
    vad: str = typer.Option(
        "pyannote", "--vad", help="VAD backend (same as WhisperX): pyannote or silero"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed cutting decisions"),
    preview: bool = typer.Option(
        False, "--preview", help="Show summary without generating files (dry-run)"
    ),
    keep_whisperx: bool = typer.Option(
        False, "--keep-whisperx", help="Keep WhisperX JSON file after processing"
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """
    Analyze a video/audio file and generate cuts for silences and filler words.

    The output can be imported into video editing software like DaVinci Resolve,
    Final Cut Pro, or Premiere Pro.
    """
    # Handle version flag
    if version:
        typer.echo(f"derush version {__version__}")
        raise typer.Exit()

    # Setup logging
    setup_logging(verbose)

    # Validate format and options
    output_format = output_format.lower()
    if output_format not in ["fcpxml", "json"]:
        error_msg = f"Invalid format '{output_format}'. Use: fcpxml or json"
        typer.echo(error_msg, err=True)
        logger.error(error_msg)
        raise typer.Exit(1)
    if vad not in ("pyannote", "silero"):
        typer.echo(f"Invalid vad_method: {vad}", err=True)
        raise typer.Exit(1)

    # Validate numeric options
    if not (1 <= chunk_size <= 120):
        error_msg = f"chunk_size must be between 1 and 120 (got {chunk_size})"
        typer.echo(error_msg, err=True)
        logger.error(error_msg)
        raise typer.Exit(1)
    if fps is not None and not (1 <= fps <= 120):
        error_msg = f"--fps must be between 1 and 120 (got {fps})"
        typer.echo(error_msg, err=True)
        logger.error(error_msg)
        raise typer.Exit(1)
    if min_silence <= 0 or min_silence > 60:
        error_msg = f"min-silence must be > 0 and <= 60 seconds (got {min_silence})"
        typer.echo(error_msg, err=True)
        logger.error(error_msg)
        raise typer.Exit(1)
    if min_gap <= 0 or min_gap > 30:
        error_msg = f"min-gap must be > 0 and <= 30 seconds (got {min_gap})"
        typer.echo(error_msg, err=True)
        logger.error(error_msg)
        raise typer.Exit(1)
    if cut_padding < 0 or cut_padding > 1:
        error_msg = f"cut-padding must be >= 0 and <= 1 second (got {cut_padding})"
        typer.echo(error_msg, err=True)
        logger.error(error_msg)
        raise typer.Exit(1)

    # [1/5] Get media info
    typer.echo("[1/5] Analyzing media file...")
    fallback_fps = fps if fps else 25.0
    try:
        media_info = get_media_info(input_file, fallback_fps=fallback_fps)
    except MediaInfoError as e:
        typer.echo("  ✗ Media info extraction failed", err=True)
        typer.echo(f"    {e}", err=True)
        logger.error(f"Media info extraction failed: {e}")
        raise typer.Exit(1) from e

    # Override FPS if specified
    if fps:
        media_info.fps = fps
        media_info.fps_rational = f"{int(fps)}/1"

    typer.echo(f"    FPS: {media_info.fps} ({media_info.fps_rational})")
    typer.echo(f"    Duration: {media_info.duration:.1f}s")
    if media_info.has_video:
        typer.echo(f"    Resolution: {media_info.width}x{media_info.height}")

    logger.debug(f"Media info extracted: {media_info}")

    # [2/5] Transcribe
    typer.echo("\n[2/5] Transcribing audio (may take several minutes)...")
    custom_fillers = [f.strip() for f in fillers.split(",")] if fillers else None

    # Output directory: next to input file when output not specified
    output_dir = output.parent if output else input_file.parent
    whisperx_output = output_dir / f"{input_file.stem}_whisperx.json"

    try:
        segments = transcribe(
            file_path=input_file,
            language=language,
            model_size=model,
            device=device,
            chunk_size=chunk_size,
            whisperx_output=whisperx_output,
            vad_method=vad,
        )
    except (RuntimeError, TranscriptionError) as e:
        typer.echo("  ✗ Transcription failed", err=True)
        typer.echo(f"    {e}", err=True)
        logger.error(f"Transcription failed: {e}")
        raise typer.Exit(1) from e
    except DerushError as e:
        typer.echo(f"  ✗ Error: {e}", err=True)
        logger.error(f"Error: {e}")
        raise typer.Exit(1) from e

    typer.echo(f"    Found {len(segments)} segments")

    # Build configuration
    config = CutterConfig(
        min_silence=min_silence,
        min_gap_cut=min_gap,
        gap_after_filler=True,
        cut_padding=cut_padding,
    )

    # Language for fillers: user-specified, or read from WhisperX output
    if language:
        detected_language = language
    else:
        # Read language from WhisperX output
        import json

        with open(whisperx_output, encoding="utf-8") as f:
            whisperx_data = json.load(f)
        detected_language = whisperx_data.get("language", "en")

    # [3/5] Run cutting pipeline
    typer.echo("\n[3/5] Correcting timestamps...")
    typer.echo(f"\n[4/5] Detecting cuts (language: {detected_language})...")

    result = run_pipeline(
        whisperx_path=whisperx_output,
        total_duration=media_info.duration,
        language=detected_language,
        custom_fillers=custom_fillers,
        config=config,
    )

    # Verbose output
    if verbose:
        typer.echo("\nWords classification:")
        for w in result.words:
            status_icon = "✗" if w.status.value == "filler" else "✓"
            typer.echo(f"  {status_icon} {w.word} ({w.start:.3f}-{w.end:.3f}) [{w.status.value}]")

        typer.echo("\nCuts:")
        for c in result.cuts:
            word_info = f" ({c.word})" if c.word else ""
            typer.echo(
                f"  [{c.start:.3f}-{c.end:.3f}] {c.cut_type.value}: {c.reason.value}{word_info}"
            )

        typer.echo("\nKeep segments:")
        for s in result.keep_segments:
            typer.echo(f"  [{s.start:.3f}-{s.end:.3f}] ({s.duration:.3f}s)")

    # Summary
    typer.echo("\nSummary:")
    typer.echo(
        f"  Words: {result.total_words} total ({result.kept_words} kept, {result.filler_words} fillers)"
    )
    if result.corrected_words > 0:
        typer.echo(f"  Timestamps corrected: {result.corrected_words} words with abnormal duration")
    typer.echo(f"  Cuts: {len(result.cuts)} sections")
    typer.echo(f"  Original duration: {result.original_duration:.1f}s")
    typer.echo(f"  Final duration: {result.final_duration:.1f}s")
    typer.echo(f"  Cut duration: {result.cut_duration:.1f}s ({result.cut_percentage:.1f}%)")

    # Padding stats (if applicable)
    if result.padding_stats and cut_padding > 0:
        stats = result.padding_stats
        typer.echo(f"\n  Padding ({cut_padding}s per side):")
        typer.echo(f"    {stats.padded_count} cuts softened")
        if stats.unchanged_count > 0:
            typer.echo(f"    {stats.unchanged_count} cuts too short, left unchanged")
        if stats.duration_regained > 0:
            typer.echo(f"    {stats.duration_regained:.2f}s regained for smoother transitions")

    # Preview mode: stop here
    if preview:
        typer.echo("\n[Preview mode - no files generated]")
        raise typer.Exit()

    # Default output path: next to input file
    if output is None:
        extension = {"fcpxml": ".fcpxml", "json": ".json"}[output_format]
        output = output_dir / f"{input_file.stem}{extension}"

    # [5/5] Export
    typer.echo(f"\n[5/5] Exporting to {output_format.upper()}...")
    exporters = {
        "fcpxml": get_fcpxml_exporter(),
        "json": JSONExporter(),
    }

    exporter = exporters[output_format]
    try:
        exporter.export(result=result, media_info=media_info, output_path=output)
    except ExportError as e:
        typer.echo("  ✗ Export failed", err=True)
        typer.echo(f"    {e}", err=True)
        logger.error(f"Export failed: {e}")
        raise typer.Exit(1) from e

    typer.echo(f"  ✓ Output saved to: {output}")

    # Cleanup WhisperX file unless user wants to keep it
    if not keep_whisperx and whisperx_output.exists():
        whisperx_output.unlink()
        logger.debug(f"Cleaned up: {whisperx_output}")


def app() -> None:
    """Entry point for the CLI."""
    typer.run(main)


if __name__ == "__main__":
    app()
