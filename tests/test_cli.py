"""Tests for CLI module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.models import Cut, MediaInfo


runner = CliRunner()


@pytest.fixture
def mock_media_info():
    """Create a mock MediaInfo for testing."""
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


class TestCLI:
    """Tests for CLI commands."""

    def test_help_displays_options(self):
        """Test that --help displays all options."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "--format" in result.stdout
        assert "--lang" in result.stdout
        assert "--min-silence" in result.stdout
        assert "--fps" in result.stdout
        assert "--model" in result.stdout

    def test_file_not_found_error(self, tmp_path):
        """Test error when input file doesn't exist."""
        non_existent = tmp_path / "nonexistent.mp4"

        result = runner.invoke(app, [str(non_existent)])

        assert result.exit_code != 0

    def test_invalid_format_error(self, tmp_path, mock_media_info, mock_whisperx):
        """Test error when invalid format is specified."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with patch("src.cli.get_media_info", return_value=mock_media_info), \
             patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            result = runner.invoke(app, [str(test_file), "--format", "invalid"])

        assert result.exit_code != 0
        assert "Invalid format" in result.stdout

    def test_fcpxml_output(self, tmp_path, mock_media_info, mock_whisperx):
        """Test that --format fcpxml generates .fcpxml file."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with patch("src.cli.get_media_info", return_value=mock_media_info), \
             patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            result = runner.invoke(app, [str(test_file), "--format", "fcpxml"])

        # Check output file was created
        output_file = test_file.with_suffix(".fcpxml")
        assert output_file.exists()
        assert "Exporting" in result.stdout

    def test_edl_output(self, tmp_path, mock_media_info, mock_whisperx):
        """Test that --format edl generates .edl file."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with patch("src.cli.get_media_info", return_value=mock_media_info), \
             patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            result = runner.invoke(app, [str(test_file), "--format", "edl"])

        # Check output file was created
        output_file = test_file.with_suffix(".edl")
        assert output_file.exists()
        assert "Exporting" in result.stdout

    def test_custom_output_path(self, tmp_path, mock_media_info, mock_whisperx):
        """Test that --output specifies custom output path."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()
        output_file = tmp_path / "custom_output.fcpxml"

        with patch("src.cli.get_media_info", return_value=mock_media_info), \
             patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            result = runner.invoke(app, [str(test_file), "--output", str(output_file)])

        assert output_file.exists()

    def test_fps_override(self, tmp_path, mock_media_info, mock_whisperx):
        """Test that --fps overrides auto-detected FPS."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with patch("src.cli.get_media_info", return_value=mock_media_info), \
             patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            result = runner.invoke(app, [str(test_file), "--fps", "30"])

        # Should show the overridden FPS
        assert "30" in result.stdout

    def test_transcription_error_handling(self, tmp_path, mock_media_info):
        """Test that transcription errors are handled gracefully."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        # Create mock whisperx that raises an error
        mock_whisperx = MagicMock()
        mock_whisperx.load_model.side_effect = RuntimeError("Transcription failed")

        with patch("src.cli.get_media_info", return_value=mock_media_info), \
             patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            result = runner.invoke(app, [str(test_file)])

        assert result.exit_code != 0
        assert "Error" in result.stdout

    def test_displays_summary(self, tmp_path, mock_media_info):
        """Test that CLI displays summary of detected cuts."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        # Create mock whisperx module with segments that will produce cuts
        mock_whisperx = MagicMock()
        mock_model = MagicMock()
        mock_whisperx.load_model.return_value = mock_model
        mock_whisperx.load_audio.return_value = MagicMock()

        # Create segments with a gap (silence) and a filler word
        mock_model.transcribe.return_value = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Hello",
                    "words": [{"word": "Hello", "start": 0.0, "end": 2.0, "score": 0.9}]
                },
                {
                    "start": 3.5,
                    "end": 5.0,
                    "text": "euh world",
                    "words": [
                        {"word": "euh", "start": 3.5, "end": 3.8, "score": 0.8},
                        {"word": "world", "start": 3.9, "end": 5.0, "score": 0.9}
                    ]
                }
            ],
            "language": "fr"
        }
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.align.return_value = mock_model.transcribe.return_value

        with patch("src.cli.get_media_info", return_value=mock_media_info), \
             patch.dict("sys.modules", {"whisperx": mock_whisperx}):
            result = runner.invoke(app, [str(test_file)])

        assert "Summary" in result.stdout
