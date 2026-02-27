"""CLI entry point for the derush tool."""

from pathlib import Path
from typing import Optional

import typer

from src import __version__
from src.config import CutterConfig
from src.cutter import run_pipeline
from src.exporters import JSONExporter, get_fcpxml_exporter, get_edl_exporter
from src.media_info import get_media_info
from src.transcriber import transcribe


def version_callback(value: bool) -> None:
    """Callback to display version and exit."""
    if value:
        typer.echo(f"derush version {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="derush",
    help="Video derushing tool - automatically detect silences and filler words for video editing"
)


@app.command()
def main(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        help="Input video or audio file (mp4, mov, mkv, wav, mp3)"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (default: same as input with appropriate extension)"
    ),
    output_format: str = typer.Option(
        "json",
        "--format", "-f",
        help="Output format: fcpxml, edl, or json"
    ),
    language: Optional[str] = typer.Option(
        None,
        "--lang", "-l",
        help="Language code (fr, en). Auto-detected if not specified."
    ),
    min_silence: float = typer.Option(
        0.5,
        "--min-silence",
        help="Minimum silence duration in seconds to cut"
    ),
    min_gap: float = typer.Option(
        0.3,
        "--min-gap",
        help="Minimum gap between words to cut (smaller gaps are kept for natural flow)"
    ),
    fillers: Optional[str] = typer.Option(
        None,
        "--fillers",
        help="Custom filler words (comma-separated)"
    ),
    fps: Optional[float] = typer.Option(
        None,
        "--fps",
        help="Override FPS (auto-detected from video by default)"
    ),
    model: str = typer.Option(
        "base",
        "--model", "-m",
        help="Whisper model size: tiny, base, small, medium, large"
    ),
    device: str = typer.Option(
        "cpu",
        "--device",
        help="Device for transcription: cpu or cuda"
    ),
    chunk_size: int = typer.Option(
        15,
        "--chunk-size",
        help="Max VAD chunk size in seconds (smaller = more segments, better filler detection)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show detailed cutting decisions"
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Show summary without generating files (dry-run)"
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit"
    ),
):
    """
    Analyze a video/audio file and generate cuts for silences and filler words.

    The output can be imported into video editing software like DaVinci Resolve,
    Final Cut Pro, or Premiere Pro.
    """
    # Validate format
    output_format = output_format.lower()
    if output_format not in ["fcpxml", "edl", "json"]:
        typer.echo(f"Error: Invalid format '{output_format}'. Use: fcpxml, edl, or json")
        raise typer.Exit(1)

    # Get media info
    typer.echo(f"Analyzing media file: {input_file}")
    fallback_fps = fps if fps else 25.0
    media_info = get_media_info(input_file, fallback_fps=fallback_fps)

    # Override FPS if specified
    if fps:
        media_info.fps = fps
        media_info.fps_rational = f"{int(fps)}/1"

    typer.echo(f"  FPS: {media_info.fps} ({media_info.fps_rational})")
    typer.echo(f"  Duration: {media_info.duration:.1f}s")
    if media_info.has_video:
        typer.echo(f"  Resolution: {media_info.width}x{media_info.height}")

    # Transcribe
    typer.echo("\nTranscribing audio...")
    custom_fillers = [f.strip() for f in fillers.split(",")] if fillers else None

    # Determine output directory for WhisperX result
    if output:
        output_dir = output.parent
        whisperx_output = output_dir / f"{input_file.stem}_whisperx.json"
    else:
        output_dir = Path.cwd() / "output"
        output_dir.mkdir(exist_ok=True)
        whisperx_output = output_dir / f"{input_file.stem}_whisperx.json"

    try:
        segments = transcribe(
            file_path=input_file,
            language=language,
            model_size=model,
            device=device,
            chunk_size=chunk_size,
            whisperx_output=whisperx_output,
        )
    except RuntimeError as e:
        typer.echo(f"Error during transcription: {e}")
        raise typer.Exit(1)

    typer.echo(f"  Found {len(segments)} segments")
    typer.echo(f"  WhisperX output saved to: {whisperx_output}")

    # Build configuration
    config = CutterConfig(
        min_silence=min_silence,
        min_gap_cut=min_gap,
        gap_after_filler=True,
    )

    # Determine language (fallback to fr if not specified)
    detected_language = language if language else "fr"

    # Run cutting pipeline
    typer.echo(f"\nRunning cutting pipeline (language: {detected_language})...")

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
            typer.echo(f"  [{c.start:.3f}-{c.end:.3f}] {c.cut_type.value}: {c.reason.value}{word_info}")

        typer.echo("\nKeep segments:")
        for s in result.keep_segments:
            typer.echo(f"  [{s.start:.3f}-{s.end:.3f}] ({s.duration:.3f}s)")

    # Summary
    typer.echo(f"\nSummary:")
    typer.echo(f"  Words: {result.total_words} total ({result.kept_words} kept, {result.filler_words} fillers)")
    typer.echo(f"  Cuts: {len(result.cuts)} sections")
    typer.echo(f"  Original duration: {result.original_duration:.1f}s")
    typer.echo(f"  Final duration: {result.final_duration:.1f}s")
    typer.echo(f"  Cut duration: {result.cut_duration:.1f}s ({result.cut_percentage:.1f}%)")

    # Preview mode: stop here
    if preview:
        typer.echo("\n[Preview mode - no files generated]")
        raise typer.Exit()

    # Determine output path
    if output is None:
        output_dir.mkdir(exist_ok=True)
        extension = {"fcpxml": ".fcpxml", "edl": ".edl", "json": ".json"}[output_format]
        output = output_dir / f"{input_file.stem}{extension}"

    # Export
    typer.echo(f"\nExporting to {output_format.upper()}...")
    exporters = {
        "fcpxml": get_fcpxml_exporter(),
        "edl": get_edl_exporter(),
        "json": JSONExporter(),
    }

    exporter = exporters[output_format]
    exporter.export(
        result=result,
        media_info=media_info,
        output_path=output
    )

    typer.echo(f"\nOutput saved to: {output}")


if __name__ == "__main__":
    app()
