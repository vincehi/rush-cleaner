"""CLI entry point for the derush tool."""

from pathlib import Path
from typing import Optional

import typer

from src import __version__
from src.exporters import FCPXMLExporter, EDLExporter, JSONExporter
from src.filler_detector import get_keep_segments
from src.media_info import get_media_info
from src.models import MediaInfo
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
        "fcpxml",
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
        help="Minimum silence duration in seconds"
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
    version: bool = typer.Option(
        False,
        "--version", "-v",
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

    # Generate cuts using "keep segments" approach (positive selection)
    detected_language = language if language else "fr"  # Default fallback
    typer.echo(f"\nAnalyzing content to keep (language: {detected_language})...")

    all_cuts = get_keep_segments(
        segments=segments,
        language=detected_language,
        custom_fillers=custom_fillers,
        min_silence=min_silence,
        total_duration=media_info.duration
    )

    typer.echo(f"  Found {len(all_cuts)} sections to cut")

    # Determine output path
    if output is None:
        # Default to output/ directory at project root
        output_dir.mkdir(exist_ok=True)
        
        extension = {"fcpxml": ".fcpxml", "edl": ".edl", "json": ".json"}[output_format]
        output = output_dir / f"{input_file.stem}{extension}"

    # Export
    typer.echo(f"\nExporting to {output_format.upper()}...")
    exporters = {
        "fcpxml": FCPXMLExporter(),
        "edl": EDLExporter(),
        "json": JSONExporter(),
    }

    exporter = exporters[output_format]
    exporter.export(cuts=all_cuts, media_info=media_info, output_path=output)

    # Summary
    total_cut_duration = sum(c.end - c.start for c in all_cuts)
    silence_count = sum(1 for c in all_cuts if c.cut_type == "silence")
    mixed_count = sum(1 for c in all_cuts if c.cut_type == "mixed")
    
    typer.echo(f"\nSummary:")
    typer.echo(f"  Total cuts: {len(all_cuts)}")
    if silence_count > 0:
        typer.echo(f"  - Silences: {silence_count}")
    if mixed_count > 0:
        typer.echo(f"  - Mixed (fillers + silences): {mixed_count}")
    typer.echo(f"  Total cut duration: {total_cut_duration:.1f}s")
    typer.echo(f"\nOutput saved to: {output}")


if __name__ == "__main__":
    app()
