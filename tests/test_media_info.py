"""Tests for media_info module."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from derush.exceptions import MediaInfoError
from derush.media_info import _parse_frame_rate, get_media_info, parse_fps_rational
from derush.models import MediaInfo


class TestParseFrameRate:
    """Tests for _parse_frame_rate function."""

    def test_parse_rational_fps(self):
        """Test parsing rational frame rates like 30000/1001."""
        assert _parse_frame_rate("30000/1001") == pytest.approx(29.97, rel=0.01)
        assert _parse_frame_rate("25/1") == 25.0
        assert _parse_frame_rate("24/1") == 24.0
        assert _parse_frame_rate("24000/1001") == pytest.approx(23.976, rel=0.01)

    def test_parse_integer_fps(self):
        """Test parsing integer frame rates."""
        assert _parse_frame_rate("30") == 30.0
        assert _parse_frame_rate("25") == 25.0
        assert _parse_frame_rate("24") == 24.0


class TestParseFpsRational:
    """Tests for parse_fps_rational (shared by FCPXML and others)."""

    def test_rational_with_slash(self):
        assert parse_fps_rational("30000/1001") == (30000, 1001)
        assert parse_fps_rational("25/1") == (25, 1)
        assert parse_fps_rational("47300/1671") == (47300, 1671)

    def test_plain_number(self):
        assert parse_fps_rational("25") == (25, 1)
        assert parse_fps_rational("30") == (30, 1)

    def test_denominator_at_least_one(self):
        # Would require "25/0" to be rejected
        assert parse_fps_rational("1/2") == (1, 2)


class TestGetMediaInfo:
    """Tests for get_media_info function."""

    def test_file_not_found(self, tmp_path):
        """Test error when file doesn't exist."""
        non_existent = tmp_path / "nonexistent.mp4"
        with pytest.raises(MediaInfoError, match="not found"):
            get_media_info(non_existent)

    @patch("derush.media_info.shutil.which")
    def test_ffprobe_not_available(self, mock_which, tmp_path):
        """Test fallback when ffprobe is not available."""
        mock_which.return_value = None

        # Create a dummy file
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        result = get_media_info(test_file, fallback_fps=25.0)

        assert result.fps == 25.0
        assert result.fps_rational == "25/1"
        assert result.has_video is False
        assert result.file_path == str(test_file.absolute())

    @patch("derush.media_info.shutil.which")
    def test_fallback_fps_rational_ntsc_and_24p(self, mock_which, tmp_path):
        """Fallback uses correct rational for 29.97 (NTSC) and 23.976 (24p)."""
        mock_which.return_value = None
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        result_2997 = get_media_info(test_file, fallback_fps=29.97)
        assert result_2997.fps == pytest.approx(29.97, rel=0.01)
        assert result_2997.fps_rational == "30000/1001"

        result_23976 = get_media_info(test_file, fallback_fps=23.976)
        assert result_23976.fps == pytest.approx(23.976, rel=0.01)
        assert result_23976.fps_rational == "24000/1001"

    @patch("derush.media_info.shutil.which")
    @patch("derush.media_info.subprocess.run")
    def test_extract_video_info(self, mock_run, mock_which, tmp_path):
        """Test extracting video metadata via ffprobe."""
        mock_which.return_value = "/usr/bin/ffprobe"

        # Create a dummy file
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        # Mock ffprobe output
        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "avg_frame_rate": "30000/1001",
                    "width": 1920,
                    "height": 1080,
                },
                {"codec_type": "audio"},
            ],
            "format": {"duration": "120.5"},
        }

        mock_result = MagicMock()
        mock_result.stdout = json.dumps(ffprobe_output)
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = get_media_info(test_file)

        assert result.fps == pytest.approx(29.97, rel=0.01)
        assert result.fps_rational == "30000/1001"
        assert result.duration == 120.5
        assert result.width == 1920
        assert result.height == 1080
        assert result.has_video is True
        assert result.nb_frames is None  # not in mock

    @patch("derush.media_info.shutil.which")
    @patch("derush.media_info.subprocess.run")
    def test_extract_video_info_includes_nb_frames(self, mock_run, mock_which, tmp_path):
        """When ffprobe returns nb_frames on the video stream, MediaInfo has it set (avoids media offline)."""
        mock_which.return_value = "/usr/bin/ffprobe"
        test_file = tmp_path / "test.mp4"
        test_file.touch()

        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "avg_frame_rate": "25/1",
                    "width": 1920,
                    "height": 1080,
                    "nb_frames": "473",
                },
                {"codec_type": "audio"},
            ],
            "format": {"duration": "19.0"},
        }

        mock_result = MagicMock()
        mock_result.stdout = json.dumps(ffprobe_output)
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = get_media_info(test_file)

        assert result.nb_frames == 473
        assert result.has_video is True

    @patch("derush.media_info.shutil.which")
    @patch("derush.media_info.subprocess.run")
    def test_audio_only_file(self, mock_run, mock_which, tmp_path):
        """Test handling audio-only files (no video stream)."""
        mock_which.return_value = "/usr/bin/ffprobe"

        test_file = tmp_path / "test.mp3"
        test_file.touch()

        ffprobe_output = {"streams": [{"codec_type": "audio"}], "format": {"duration": "60.0"}}

        mock_result = MagicMock()
        mock_result.stdout = json.dumps(ffprobe_output)
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = get_media_info(test_file, fallback_fps=25.0)

        assert result.has_video is False
        assert result.fps == 25.0
        assert result.width == 0
        assert result.height == 0

    @patch("derush.media_info.shutil.which")
    @patch("derush.media_info.subprocess.run")
    def test_ffprobe_failure(self, mock_run, mock_which, tmp_path):
        """Test error handling when ffprobe fails."""
        mock_which.return_value = "/usr/bin/ffprobe"

        test_file = tmp_path / "test.mp4"
        test_file.touch()

        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["ffprobe"], stderr="Error: invalid file"
        )

        with pytest.raises(MediaInfoError, match="ffprobe failed"):
            get_media_info(test_file)


class TestMediaInfoMethods:
    """Tests for MediaInfo class methods."""

    @pytest.fixture
    def media_info(self):
        """Create a sample MediaInfo instance."""
        return MediaInfo(
            fps=25.0,
            fps_rational="25/1",
            duration=120.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4",
        )

    def test_total_frames(self, media_info):
        """Test total_frames property."""
        assert media_info.total_frames == 3000  # 120s * 25fps

    def test_seconds_to_frames(self, media_info):
        """Test seconds_to_frames conversion."""
        assert media_info.seconds_to_frames(1.0) == 25
        assert media_info.seconds_to_frames(10.0) == 250

    def test_seconds_to_timecode_non_drop(self, media_info):
        """Test timecode conversion for non-drop-frame."""
        assert media_info.seconds_to_timecode(0.0) == "00:00:00:00"
        assert media_info.seconds_to_timecode(1.0) == "00:00:01:00"
        assert media_info.seconds_to_timecode(65.5) == "00:01:05:12"  # 65.5s at 25fps

    def test_seconds_to_timecode_drop_frame(self):
        """Test timecode conversion for drop-frame (29.97fps)."""
        media_info = MediaInfo(
            fps=29.97,
            fps_rational="30000/1001",
            duration=120.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4",
        )

        # Drop-frame uses semicolon before frames
        tc = media_info.seconds_to_timecode(0.0)
        assert ";" in tc  # Drop-frame separator
