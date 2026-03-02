"""Tests for CLI module."""

from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from derush import __version__
from derush.cli import main

runner = CliRunner()

# Create a Typer app for testing (use _cli prefix to avoid pytest collection warning)
_cli_app = typer.Typer()
_cli_app.command()(main)


class TestCLI:
    """Tests for CLI commands."""

    def test_help_displays_options(self):
        """Test that --help displays all options."""
        result = runner.invoke(_cli_app, ["--help"])

        assert result.exit_code == 0
        assert "--format" in result.stdout
        assert "--lang" in result.stdout
        assert "--min-silence" in result.stdout
        assert "--cut-padding" in result.stdout
        assert "--fps" in result.stdout
        assert "--model" in result.stdout
        assert "--version" in result.stdout

    def test_version_displays_version(self, tmp_path):
        """Test that --version displays version."""
        # Create a dummy file since input_file is required
        test_file = tmp_path / "dummy.mp4"
        test_file.touch()
        result = runner.invoke(_cli_app, [str(test_file), "--version"])

        assert result.exit_code == 0
        assert __version__ in result.stdout

    def test_file_not_found_error(self, tmp_path):
        """Test error when input file doesn't exist."""
        non_existent = tmp_path / "nonexistent.mp4"

        result = runner.invoke(_cli_app, [str(non_existent)])

        assert result.exit_code != 0

    def test_invalid_format_error(self, tmp_path, sample_media_info, mock_whisperx):
        """Test error when invalid format is specified."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with (
            patch("derush.cli.get_media_info", return_value=sample_media_info),
            patch.dict("sys.modules", {"whisperx": mock_whisperx}),
        ):
            result = runner.invoke(_cli_app, [str(test_file), "--format", "invalid"])

        assert result.exit_code != 0
        assert "Invalid format" in (result.stdout + result.stderr)

    def test_fcpxml_output(self, tmp_path, sample_media_info, mock_whisperx):
        """Test that --format fcpxml generates .fcpxml file."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()
        output_file = tmp_path / "test.fcpxml"

        with (
            patch("derush.cli.get_media_info", return_value=sample_media_info),
            patch.dict("sys.modules", {"whisperx": mock_whisperx}),
        ):
            result = runner.invoke(
                _cli_app, [str(test_file), "--format", "fcpxml", "-o", str(output_file)]
            )

        assert output_file.exists()
        assert "Exporting" in result.stdout

    def test_custom_output_path(self, tmp_path, sample_media_info, mock_whisperx):
        """Test that --output specifies custom output path."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()
        output_file = tmp_path / "custom_output.fcpxml"

        with (
            patch("derush.cli.get_media_info", return_value=sample_media_info),
            patch.dict("sys.modules", {"whisperx": mock_whisperx}),
        ):
            result = runner.invoke(_cli_app, [str(test_file), "--output", str(output_file)])

        assert output_file.exists()

    def test_default_output_next_to_input(self, tmp_path, sample_media_info, mock_whisperx):
        """Test that without -o, output is created next to the input file."""
        test_file = tmp_path / "my_video.mp4"
        test_file.touch()

        with (
            patch("derush.cli.get_media_info", return_value=sample_media_info),
            patch.dict("sys.modules", {"whisperx": mock_whisperx}),
        ):
            result = runner.invoke(_cli_app, [str(test_file)])

        assert result.exit_code == 0
        assert (tmp_path / "my_video.fcpxml").exists()
        assert (tmp_path / "my_video_whisperx.json").exists()

    def test_fps_override(self, tmp_path, sample_media_info, mock_whisperx):
        """Test that --fps overrides auto-detected FPS."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        with (
            patch("derush.cli.get_media_info", return_value=sample_media_info),
            patch.dict("sys.modules", {"whisperx": mock_whisperx}),
        ):
            result = runner.invoke(_cli_app, [str(test_file), "--fps", "30"])

        # Should show the overridden FPS
        assert "30" in result.stdout

    def test_transcription_error_handling(self, tmp_path, sample_media_info):
        """Test that transcription errors are handled gracefully."""
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        # Create mock whisperx that raises an error
        mock_whisperx = MagicMock()
        mock_whisperx.load_model.side_effect = RuntimeError("Transcription failed")

        with (
            patch("derush.cli.get_media_info", return_value=sample_media_info),
            patch.dict("sys.modules", {"whisperx": mock_whisperx}),
        ):
            result = runner.invoke(_cli_app, [str(test_file)])

        assert result.exit_code != 0
        assert "Transcription failed" in (result.stdout + result.stderr)

    def test_displays_summary(self, tmp_path, sample_media_info):
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
                    "words": [{"word": "Hello", "start": 0.0, "end": 2.0, "score": 0.9}],
                },
                {
                    "start": 3.5,
                    "end": 5.0,
                    "text": "euh world",
                    "words": [
                        {"word": "euh", "start": 3.5, "end": 3.8, "score": 0.8},
                        {"word": "world", "start": 3.9, "end": 5.0, "score": 0.9},
                    ],
                },
            ],
            "language": "fr",
        }
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.align.return_value = mock_model.transcribe.return_value

        with (
            patch("derush.cli.get_media_info", return_value=sample_media_info),
            patch.dict("sys.modules", {"whisperx": mock_whisperx}),
        ):
            result = runner.invoke(_cli_app, [str(test_file)])

        assert "Summary" in result.stdout
