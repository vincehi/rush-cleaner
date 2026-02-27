"""Data models for the derush tool."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Word:
    """Represents a single word with timing information."""
    word: str
    start: float  # In seconds
    end: float    # In seconds
    score: float  # Confidence score from WhisperX


@dataclass
class Segment:
    """Represents a transcribed segment with timing."""
    start: float        # In seconds
    end: float          # In seconds
    text: str
    words: list[Word]   # Word-level alignment from WhisperX


@dataclass
class Cut:
    """Represents a segment to cut from the video."""
    start: float        # In seconds
    end: float          # In seconds
    cut_type: str       # "silence" | "filler"
    label: str          # Ex: "Silence 1.2s" | "Filler: euh"


@dataclass
class MediaInfo:
    """Video/Audio file metadata."""
    fps: float              # Ex: 29.97, 25.0, 24.0
    fps_rational: str       # Ex: "30000/1001", "25/1"
    duration: float         # In seconds
    width: int              # Video width in pixels
    height: int             # Video height in pixels
    has_video: bool         # True for video files, False for audio-only
    file_path: str          # Absolute path to the source file

    @property
    def total_frames(self) -> int:
        """Total number of frames in the video."""
        return int(self.duration * self.fps)

    def seconds_to_frames(self, seconds: float) -> int:
        """Convert seconds to frame number."""
        return int(seconds * self.fps)

    def seconds_to_timecode(self, seconds: float) -> str:
        """
        Convert seconds to timecode string (HH:MM:SS:FF).
        Handles drop-frame for 29.97fps.
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frames = int((seconds % 1) * self.fps)

        # Drop-frame notation for 29.97fps (use semicolon before frames)
        separator = ";" if abs(self.fps - 29.97) < 0.01 else ":"

        return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{frames:02d}"
