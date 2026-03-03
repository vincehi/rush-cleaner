"""Media information extraction using ffprobe."""

import json
import shutil
import subprocess
from pathlib import Path

from derush.exceptions import MediaInfoError
from derush.models import MediaInfo


def get_media_info(file_path: Path, fallback_fps: float = 25.0) -> MediaInfo:
    """
    Extract media information from video/audio file using ffprobe.

    Args:
        file_path: Path to the media file
        fallback_fps: FPS to use if ffprobe is unavailable or for audio-only files

    Returns:
        MediaInfo object with extracted metadata

    Raises:
        MediaInfoError: If the file doesn't exist or ffprobe fails
    """
    if not file_path.exists():
        raise MediaInfoError(f"Media file not found: {file_path}") from None

    # Check if ffprobe is available
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path is None:
        raise MediaInfoError(
            "ffprobe not found. Install ffmpeg:\n"
            "  macOS:   brew install ffmpeg\n"
            "  Ubuntu:  sudo apt install ffmpeg\n"
            "  Windows: winget install ffmpeg"
        )

    # Run ffprobe to get stream information
    cmd = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(file_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise MediaInfoError(
            f"Could not analyze media file: {file_path}\n"
            f"  - Check that the file is not corrupted\n"
            f"  - Try: ffprobe {file_path}\n"
            f"  Error: {e.stderr.strip() if e.stderr else 'unknown'}"
        ) from e
    except json.JSONDecodeError as e:
        raise MediaInfoError(
            f"Could not parse ffprobe output for: {file_path}\n"
            f"  - The file format may be unsupported\n"
            f"  Error: {e}"
        ) from e

    return _parse_ffprobe_output(file_path, data, fallback_fps)


def _parse_ffprobe_output(file_path: Path, data: dict, fallback_fps: float) -> MediaInfo:
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

    nb_frames: int | None = None
    audio_sample_rate: int | None = None
    audio_channels: int | None = None
    if has_video:
        # Extract FPS and frame count from video stream (nb_frames avoids FCPXML "media offline")
        fps_rational = video_stream.get("avg_frame_rate", "25/1")
        fps = _parse_frame_rate(fps_rational)
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        nb_frames_raw = video_stream.get("nb_frames")
        if nb_frames_raw is not None:
            try:
                nb_frames = int(nb_frames_raw)
            except (TypeError, ValueError):
                pass
    else:
        # Audio-only file
        fps_rational = f"{int(fallback_fps)}/1"
        fps = fallback_fps
        width = 0
        height = 0

    if audio_stream is not None:
        try:
            audio_sample_rate = int(audio_stream.get("sample_rate", 0)) or None
        except (TypeError, ValueError):
            pass
        try:
            audio_channels = int(audio_stream.get("channels", 0)) or None
        except (TypeError, ValueError):
            pass

    return MediaInfo(
        fps=fps,
        fps_rational=fps_rational,
        duration=duration,
        width=width,
        height=height,
        has_video=has_video,
        file_path=str(file_path.absolute()),
        nb_frames=nb_frames,
        audio_sample_rate=audio_sample_rate,
        audio_channels=audio_channels,
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


def parse_fps_rational(fps_rational: str) -> tuple[int, int]:
    """
    Parse fps_rational string to (numerator, denominator) for frame-based math.

    Handles "num/den" (e.g. "30000/1001", "25/1") and plain numbers ("25", "29.97").
    Single source of truth for FCPXML and any exporter needing frame-accurate rationals.

    Returns:
        (fps_num, fps_den) with fps_den >= 1.
    """
    if "/" in fps_rational:
        num_s, den_s = fps_rational.split("/", 1)
        num = int(num_s)
        den = max(1, int(den_s))
        return (num, den)
    # Plain number → treat as integer fps, or 29.97 → 30000/1001 would need extra logic
    num = int(float(fps_rational))
    return (num, 1)
