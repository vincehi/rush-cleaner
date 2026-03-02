"""Data models for the derush tool."""

from dataclasses import dataclass
from enum import Enum


class WordStatus(str, Enum):
    """Status of a word in the cutting pipeline."""

    KEPT = "kept"
    FILLER = "filler"


class CutType(str, Enum):
    """Type of cut."""

    SILENCE = "silence"
    FILLER = "filler"
    GAP = "gap"
    MIXED = "mixed"


class CutReason(str, Enum):
    """Reason for a cut."""

    GAP_BEFORE_SPEECH = "gap_before_speech"
    GAP_AFTER_SPEECH = "gap_after_speech"
    GAP_BETWEEN_SEGMENTS = "gap_between_segments"
    FILLER_WORD = "filler_word"
    GAP_AFTER_FILLER = "gap_after_filler"
    MERGED = "merged"


# Timecode constants
NTSC_FPS = 29.97
NTSC_FPS_TOLERANCE = 0.01


@dataclass
class Segment:
    """Represents a transcription segment with multiple words."""

    start: float  # In seconds
    end: float  # In seconds
    text: str  # Full text of the segment
    words: list["Word"]  # Word-level timestamps


@dataclass
class Word:
    """Represents a single word with timing information."""

    word: str
    start: float  # In seconds
    end: float  # In seconds
    score: float  # Confidence score from WhisperX
    status: WordStatus = WordStatus.KEPT  # Set during classification


@dataclass
class Cut:
    """Represents a segment to cut from the video."""

    start: float  # In seconds
    end: float  # In seconds
    cut_type: CutType  # Type of cut
    reason: CutReason  # Why this cut was made
    word: str | None = None  # For filler cuts, the word that was cut


@dataclass
class KeepSegment:
    """Represents a segment to keep in the final video."""

    start: float  # In seconds
    end: float  # In seconds

    @property
    def duration(self) -> float:
        """Duration of the segment in seconds."""
        return self.end - self.start


@dataclass
class CutterResult:
    """Result of the cutting pipeline."""

    words: list[Word]  # All words with their status
    cuts: list[Cut]  # Segments to cut
    keep_segments: list[KeepSegment]  # Segments to keep

    # Summary stats
    total_words: int
    kept_words: int
    filler_words: int
    original_duration: float
    final_duration: float
    cut_duration: float

    @property
    def cut_percentage(self) -> float:
        """Percentage of the video that will be cut."""
        if self.original_duration == 0:
            return 0.0
        return (self.cut_duration / self.original_duration) * 100


def merge_adjacent_cuts(cuts: list[Cut]) -> list[Cut]:
    """
    Merge overlapping or adjacent cuts into single cuts.

    Args:
        cuts: List of cuts (potentially unsorted and overlapping)

    Returns:
        List of merged cuts, sorted by start time
    """
    if not cuts:
        return []

    # Sort cuts by start time
    sorted_cuts = sorted(cuts, key=lambda c: c.start)

    merged = [sorted_cuts[0]]

    for current in sorted_cuts[1:]:
        previous = merged[-1]

        # Check if current cut overlaps or is adjacent to the previous one
        if current.start <= previous.end:
            # Determine merged type
            if previous.cut_type == current.cut_type:
                merged_type = previous.cut_type
            else:
                merged_type = CutType.MIXED

            merged[-1] = Cut(
                start=previous.start,
                end=max(previous.end, current.end),
                cut_type=merged_type,
                reason=CutReason.MERGED,
                word=None,
            )
        else:
            merged.append(current)

    return merged


@dataclass
class MediaInfo:
    """Video/Audio file metadata."""

    fps: float  # Ex: 29.97, 25.0, 24.0
    fps_rational: str  # Ex: "30000/1001", "25/1"
    duration: float  # In seconds (from container format)
    width: int  # Video width in pixels
    height: int  # Video height in pixels
    has_video: bool  # True for video files, False for audio-only
    file_path: str  # Absolute path to the source file
    nb_frames: int | None = (
        None  # Video stream frame count when available (avoids media offline)
    )
    audio_sample_rate: int | None = None  # From ffprobe when available (e.g. 48000, 44100)
    audio_channels: int | None = None  # From ffprobe when available (1=mono, 2=stereo)

    @property
    def total_frames(self) -> int:
        """Total number of frames in the video.

        Uses nb_frames from the video stream when available (frame-accurate);
        otherwise falls back to duration * fps.
        """
        if self.nb_frames is not None and self.nb_frames > 0:
            return self.nb_frames
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
        separator = ";" if abs(self.fps - NTSC_FPS) < NTSC_FPS_TOLERANCE else ":"

        return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{frames:02d}"
