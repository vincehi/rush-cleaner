"""Tests for transcriber module."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

import pytest

from derush.models import Segment, Word
from derush.transcriber import transcribe


class TestTranscribe:
    """Tests for transcribe function."""

    def test_file_not_found(self, tmp_path):
        """Test error when file doesn't exist."""
        non_existent = tmp_path / "nonexistent.mp4"

        with pytest.raises(FileNotFoundError):
            transcribe(non_existent)

    def test_transcribe_returns_segments(self, tmp_path):
        """Test that transcribe returns list of segments."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        # Create mock whisperx module
        mock_whisperx = MagicMock()

        # Mock model
        mock_model = MagicMock()
        mock_whisperx.load_model.return_value = mock_model

        # Mock audio
        mock_whisperx.load_audio.return_value = MagicMock()

        # Mock transcription result
        mock_model.transcribe.return_value = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Hello world",
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 0.5, "score": 0.9},
                        {"word": "world", "start": 0.6, "end": 1.0, "score": 0.8}
                    ]
                }
            ],
            "language": "en"
        }

        # Mock alignment
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.align.return_value = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Hello world",
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 0.5, "score": 0.9},
                        {"word": "world", "start": 0.6, "end": 1.0, "score": 0.8}
                    ]
                }
            ]
        }

        with patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            result = transcribe(test_file, language="en", model_size="base", device="cpu")

        assert len(result) == 1
        assert isinstance(result[0], Segment)
        assert result[0].text == "Hello world"
        assert result[0].start == 0.0
        assert result[0].end == 2.0

        # Check words
        assert len(result[0].words) == 2
        assert result[0].words[0].word == "Hello"
        assert result[0].words[0].start == 0.0
        assert result[0].words[0].end == 0.5

    def test_transcribe_with_word_timestamps(self, tmp_path):
        """Test that word-level timestamps are preserved."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        # Create mock whisperx module
        mock_whisperx = MagicMock()

        # Mock model
        mock_model = MagicMock()
        mock_whisperx.load_model.return_value = mock_model
        mock_whisperx.load_audio.return_value = MagicMock()

        mock_model.transcribe.return_value = {
            "segments": [],
            "language": "en"
        }

        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.align.return_value = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Test sentence",
                    "words": [
                        {"word": "Test", "start": 0.0, "end": 0.5, "score": 0.95},
                        {"word": "sentence", "start": 0.6, "end": 1.2, "score": 0.92}
                    ]
                }
            ]
        }

        with patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            result = transcribe(test_file)

        # Check that words have individual timestamps
        words = result[0].words
        assert words[0].start < words[1].start
        assert words[0].end > words[0].start

    def test_transcribe_auto_detect_language(self, tmp_path):
        """Test that language is auto-detected when not specified."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        # Create mock whisperx module
        mock_whisperx = MagicMock()

        mock_model = MagicMock()
        mock_whisperx.load_model.return_value = mock_model
        mock_whisperx.load_audio.return_value = MagicMock()

        mock_model.transcribe.return_value = {
            "segments": [],
            "language": "fr"  # Auto-detected French
        }

        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.align.return_value = {"segments": []}

        with patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            result = transcribe(test_file, language=None)

        # Should have called transcribe without language specified
        mock_model.transcribe.assert_called_once()
        call_kwargs = mock_model.transcribe.call_args[1]
        assert "language" not in call_kwargs or call_kwargs["language"] is None

    def test_whisperx_not_installed(self, tmp_path):
        """Test error when whisperx is not installed."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        # Remove whisperx from modules if present
        with patch.dict("sys.modules", {"whisperx": None}):
            with pytest.raises(RuntimeError, match="whisperx is not installed"):
                transcribe(test_file)

    def test_empty_transcription(self, tmp_path):
        """Test handling of empty transcription (silent file)."""
        test_file = tmp_path / "silent.mp4"
        test_file.touch()

        # Create mock whisperx module
        mock_whisperx = MagicMock()

        mock_model = MagicMock()
        mock_whisperx.load_model.return_value = mock_model
        mock_whisperx.load_audio.return_value = MagicMock()

        mock_model.transcribe.return_value = {
            "segments": [],
            "language": "en"
        }

        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.align.return_value = {"segments": []}

        with patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            result = transcribe(test_file)

        assert len(result) == 0
