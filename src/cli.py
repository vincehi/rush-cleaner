"""CLI entry point for the derush tool."""

from pathlib import Path
from typing import Optional

import typer

from src.exporters import FCPXMLExporter, EDLExporter, JSONExporter
from src.filler_detector import detect_fillers
from src.media_info import get_media_info
from src.models import MediaInfo
from src.silence_detector import detect_silences
from src.transcriber import transcribe

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
    format: str = typer.Option(
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
):
    """
    Analyze a video/audio file and generate cuts for silences and filler words.

    The output can be imported into video editing software like DaVinci Resolve,
    Final Cut Pro, or Premiere Pro.
    """
    # Validate format
    format = format.lower()
    if format not in ["fcpxml", "edl", "json"]:
        typer.echo(f"Error: Invalid format '{format}'. Use: fcpxml, edl, or json")
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

    try:
        segments = transcribe(
            file_path=input_file,
            language=language,
            model_size=model,
            device=device
        )
    except RuntimeError as e:
        typer.echo(f"Error during transcription: {e}")
        raise typer.Exit(1)

    typer.echo(f"  Found {len(segments)} segments")

    # Detect silences
    typer.echo("\nDetecting silences...")
    silences = detect_silences(
        segments=segments,
        min_duration=min_silence,
        total_duration=media_info.duration
    )
    typer.echo(f"  Found {len(silences)} silences")

    # Detect fillers
    detected_language = language if language else "fr"  # Default fallback
    typer.echo(f"\nDetecting filler words (language: {detected_language})...")
    fillers_detected = detect_fillers(
        segments=segments,
        language=detected_language,
        custom_fillers=custom_fillers
    )
    typer.echo(f"  Found {len(fillers_detected)} filler words")

    # Combine all cuts
    all_cuts = silences + fillers_detected

    # Determine output path
    if output is None:
        # Default to output/ directory at project root
        output_dir = Path.cwd() / "output"
        output_dir.mkdir(exist_ok=True)
        
        extension = {"fcpxml": ".fcpxml", "edl": ".edl", "json": ".json"}[format]
        output = output_dir / f"{input_file.stem}{extension}"

    # Export
    typer.echo(f"\nExporting to {format.upper()}...")
    exporters = {
        "fcpxml": FCPXMLExporter(),
        "edl": EDLExporter(),
        "json": JSONExporter(),
    }

    exporter = exporters[format]
    exporter.export(cuts=all_cuts, media_info=media_info, output_path=output)

    # Summary
    total_cut_duration = sum(c.end - c.start for c in all_cuts)
    typer.echo(f"\nSummary:")
    typer.echo(f"  Total cuts: {len(all_cuts)}")
    typer.echo(f"  - Silences: {len(silences)}")
    typer.echo(f"  - Fillers: {len(fillers_detected)}")
    typer.echo(f"  Total cut duration: {total_cut_duration:.1f}s")
    typer.echo(f"\nOutput saved to: {output}")


if __name__ == "__main__":
    app()
