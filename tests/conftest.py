"""Shared fixtures for tests."""

from unittest.mock import MagicMock

import pytest

from src.models import Cut, MediaInfo


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
        file_path="/path/to/video.mp4"
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
        file_path="/path/to/video.mp4"
    )


@pytest.fixture
def sample_cuts():
    """Create sample cuts for testing."""
    return [
        Cut(start=2.0, end=3.2, cut_type="silence", label="Silence 1.2s"),
        Cut(start=15.0, end=15.3, cut_type="filler", label="Filler: euh"),
        Cut(start=5.0, end=6.0, cut_type="silence", label="Silence 1.0s"),
    ]


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
            ]
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
            ]
        },
    ]
