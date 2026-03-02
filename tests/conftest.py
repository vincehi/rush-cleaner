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
    """Create sample cutter result for testing."""
    words = [
        Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
        Word(word="world", start=0.6, end=1.0, score=0.9, status=WordStatus.KEPT),
        Word(word="euh", start=15.0, end=15.3, score=0.8, status=WordStatus.FILLER),
    ]

    keep_segments = [
        KeepSegment(start=0.0, end=2.0),
        KeepSegment(start=3.2, end=5.0),
        KeepSegment(start=6.0, end=15.0),
        KeepSegment(start=15.3, end=60.0),
    ]

    return CutterResult(
        words=words,
        cuts=sample_cuts,
        keep_segments=keep_segments,
        total_words=3,
        kept_words=2,
        filler_words=1,
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
