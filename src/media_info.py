"""Media information extraction using ffprobe."""

import json
import shutil
import subprocess
from pathlib import Path

from src.models import MediaInfo


def get_media_info(file_path: Path, fallback_fps: float = 25.0) -> MediaInfo:
    """
    Extract media information from video/audio file using ffprobe.

    Args:
        file_path: Path to the media file
        fallback_fps: FPS to use if ffprobe is unavailable or for audio-only files

    Returns:
        MediaInfo object with extracted metadata

    Raises:
        FileNotFoundError: If the input file doesn't exist
        RuntimeError: If ffprobe fails to extract information
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Media file not found: {file_path}")

    # Check if ffprobe is available
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path is None:
        # Fallback: return basic info without video metadata
        return _get_fallback_media_info(file_path, fallback_fps)

    # Run ffprobe to get stream information
    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(file_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse ffprobe output: {e}") from e

    return _parse_ffprobe_output(file_path, data, fallback_fps)


def _parse_ffprobe_output(
    file_path: Path,
    data: dict,
    fallback_fps: float
) -> MediaInfo:
    """Parse ffprobe JSON output into MediaInfo."""
    streams = data.get("streams", [])
    format_info = data.get("format", {})

    # Get duration from format (more reliable)
    duration = float(format_info.get("duration", 0.0))

    # Find video stream
    video_stream = None
    audio_stream = None

    for stream in streams:
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        elif stream.get("codec_type") == "audio" and audio_stream is None:
            audio_stream = stream

    has_video = video_stream is not None

    if has_video:
        # Extract FPS from video stream
        fps_rational = video_stream.get("avg_frame_rate", "25/1")
        fps = _parse_frame_rate(fps_rational)
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
    else:
        # Audio-only file
        fps_rational = f"{int(fallback_fps)}/1"
        fps = fallback_fps
        width = 0
        height = 0

    return MediaInfo(
        fps=fps,
        fps_rational=fps_rational,
        duration=duration,
        width=width,
        height=height,
        has_video=has_video,
        file_path=str(file_path.absolute())
    )


def _parse_frame_rate(frame_rate: str) -> float:
    """
    Parse frame rate string (e.g., "30000/1001") to float.

    Args:
        frame_rate: Frame rate as string (e.g., "30000/1001", "25/1", "30")

    Returns:
        Frame rate as float (e.g., 29.97, 25.0, 30.0)
    """
    if "/" in frame_rate:
        num, denom = frame_rate.split("/")
        return float(num) / float(denom)
    return float(frame_rate)


def _get_fallback_media_info(file_path: Path, fallback_fps: float) -> MediaInfo:
    """Return basic MediaInfo when ffprobe is unavailable."""
    return MediaInfo(
        fps=fallback_fps,
        fps_rational=f"{int(fallback_fps)}/1",
        duration=0.0,  # Unknown without ffprobe
        width=0,
        height=0,
        has_video=False,  # Conservative assumption
        file_path=str(file_path.absolute())
    )
