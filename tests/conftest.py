"""Shared fixtures for tests."""

from unittest.mock import MagicMock

import pytest

from derush.models import (
    Cut,
    CutReason,
    CutterResult,
    CutType,
    KeepSegment,
    MediaInfo,
    Word,
    WordStatus,
)


@pytest.fixture
def sample_media_info():
    """Create sample media info for testing."""
    return MediaInfo(
        fps=25.0,
        fps_rational="25/1",
        duration=60.0,
        width=1920,
        height=1080,
        has_video=True,
        file_path="/path/to/video.mp4",
    )


@pytest.fixture
def sample_media_info_2997():
    """Create sample media info with 29.97fps (drop-frame)."""
    return MediaInfo(
        fps=29.97,
        fps_rational="30000/1001",
        duration=60.0,
        width=1920,
        height=1080,
        has_video=True,
        file_path="/path/to/video.mp4",
    )


@pytest.fixture
def sample_cuts():
    """Create sample cuts for testing."""
    return [
        Cut(start=2.0, end=3.2, cut_type=CutType.SILENCE, reason=CutReason.GAP_BETWEEN_SEGMENTS),
        Cut(
            start=15.0, end=15.3, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD, word="euh"
        ),
        Cut(start=5.0, end=6.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BETWEEN_SEGMENTS),
    ]


@pytest.fixture
def sample_cutter_result(sample_cuts):
    """Create sample cutter result for testing.

    Words are spread across the timeline to match keep_segments structure:
    - [0.0-1.0]: "Hello", "world" (consecutive KEPT words)
    - [1.0-2.0]: gap (silence)
    - [2.0-3.2]: cut (silence)
    - [3.2-3.5]: "content" (isolated KEPT word)
    - [3.5-4.0]: gap (silence)
    - [4.0-4.5]: "here" (isolated KEPT word)
    - [4.5-6.0]: gap (silence)
    - [5.0-6.0]: cut (silence)
    - [6.0-15.0]: gap (silence)
    - [15.0-15.3]: "euh" (FILLER)
    - [15.3-60.0]: gap (silence after filler)
    """
    words = [
        # Group 1: [0.0-1.0] - "Hello" and "world" are consecutive
        Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
        Word(word="world", start=0.6, end=1.0, score=0.9, status=WordStatus.KEPT),
        # Gap [1.0-2.0] - silence between groups
        # Group 2: [3.2-3.5] - isolated word "content"
        Word(word="content", start=3.2, end=3.5, score=0.9, status=WordStatus.KEPT),
        # Gap [3.5-4.0] - silence between groups
        # Group 3: [4.0-4.5] - isolated word "here"
        Word(word="here", start=4.0, end=4.5, score=0.9, status=WordStatus.KEPT),
        # Gap [4.5-6.0] - silence between groups
        # Filler: [15.0-15.3] - creates a break
        Word(word="euh", start=15.0, end=15.3, score=0.8, status=WordStatus.FILLER),
        # Group 4: [20.0-25.0] - words after filler
        Word(word="final", start=20.0, end=20.5, score=0.9, status=WordStatus.KEPT),
        Word(word="words", start=20.6, end=21.0, score=0.9, status=WordStatus.KEPT),
    ]

    keep_segments = [
        KeepSegment(start=0.0, end=2.0),  # "Hello" + "world" + gap
        KeepSegment(start=3.2, end=5.0),  # "content" + gaps
        KeepSegment(start=6.0, end=15.0),  # "here" + gap + silence + filler
        KeepSegment(start=15.3, end=60.0),  # Empty after filler
    ]

    return CutterResult(
        words=words,
        cuts=sample_cuts,
        keep_segments=keep_segments,
        total_words=6,
        kept_words=5,
        filler_words=1,
        corrected_words=0,
        original_duration=60.0,
        final_duration=57.5,
        cut_duration=2.5,
    )


@pytest.fixture
def mock_whisperx():
    """Create a mock whisperx module."""
    mock = MagicMock()
    mock_model = MagicMock()
    mock.load_model.return_value = mock_model
    mock.load_audio.return_value = MagicMock()
    mock_model.transcribe.return_value = {"segments": [], "language": "fr"}
    mock.load_align_model.return_value = (MagicMock(), MagicMock())
    mock.align.return_value = {"segments": []}
    return mock


@pytest.fixture
def sample_segments():
    """Create sample transcription segments for testing."""
    return [
        {
            "start": 0.0,
            "end": 5.0,
            "text": "Bonjour, ceci est un test.",
            "words": [
                {"word": "bonjour", "start": 0.0, "end": 0.5},
                {"word": "ceci", "start": 0.6, "end": 0.9},
                {"word": "est", "start": 1.0, "end": 1.2},
                {"word": "un", "start": 1.3, "end": 1.5},
                {"word": "test", "start": 1.6, "end": 2.0},
            ],
        },
        {
            "start": 7.0,
            "end": 12.0,
            "text": "Euh, voici une deuxième phrase.",
            "words": [
                {"word": "euh", "start": 7.0, "end": 7.3},
                {"word": "voici", "start": 7.5, "end": 8.0},
                {"word": "une", "start": 8.1, "end": 8.3},
                {"word": "deuxième", "start": 8.4, "end": 9.0},
                {"word": "phrase", "start": 9.1, "end": 9.5},
            ],
        },
    ]
