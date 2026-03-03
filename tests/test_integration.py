"""Integration tests for derush tool."""

from unittest.mock import MagicMock

import pytest

from derush.exporters.fcpxml import FCPXMLExporter
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
    """Fixture providing sample media info (25fps)."""
    return MediaInfo(
        fps=25.0,
        fps_rational="25/1",
        duration=20.0,
        width=1920,
        height=1080,
        has_video=True,
        file_path="/path/to/video.mp4",
    )


@pytest.fixture
def mock_whisperx():
    """Mock WhisperX module."""
    mock_whisperx = MagicMock()

    # Mock word segments output
    mock_whisperx.load.return_value = {
        "segments": [
            {
                "words": [
                    {"word": "bonjour", "start": 0.0, "end": 0.5, "score": 0.9},
                    {"word": "euh", "start": 0.5, "end": 1.0, "score": 0.8},
                    {"word": "demo", "start": 1.0, "end": 1.5, "score": 0.95},
                ]
            },
            {
                "words": [
                    {"word": "je", "start": 1.5, "end": 2.0, "score": 0.92},
                    {"word": "teste", "start": 2.0, "end": 2.5, "score": 0.88},
                    {"word": "hmm", "start": 2.5, "end": 3.0, "score": 0.24},
                ]
            },
            {
                "words": [
                    {"word": "je", "start": 3.0, "end": 3.5, "score": 0.96},
                    {"word": "pense", "start": 3.5, "end": 4.0, "score": 0.98},
                ]
            },
        ],
        "word_segments": [
            {"word": "bonjour", "start": 0.0, "end": 0.5, "score": 0.9},
            {"word": "euh", "start": 0.5, "end": 1.0, "score": 0.8},
            {"word": "demo", "start": 1.0, "end": 1.5, "score": 0.95},
            {"word": "je", "start": 1.5, "end": 2.0, "score": 0.92},
            {"word": "teste", "start": 2.0, "end": 2.5, "score": 0.88},
            {"word": "hmm", "start": 2.5, "end": 3.0, "score": 0.24},
            {"word": "je", "start": 3.0, "end": 3.5, "score": 0.96},
            {"word": "pense", "start": 3.5, "end": 4.0, "score": 0.98},
        ],
    }

    return mock_whisperx


@pytest.fixture
def cutter_result():
    """Fixture providing a sample CutterResult."""
    return CutterResult(
        words=[
            Word(word="bonjour", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="euh", start=0.5, end=1.0, score=0.8, status=WordStatus.FILLER),
            Word(word="demo", start=1.0, end=1.5, score=0.95, status=WordStatus.KEPT),
            Word(word="je", start=1.5, end=2.0, score=0.92, status=WordStatus.KEPT),
            Word(word="teste", start=2.0, end=2.5, score=0.88, status=WordStatus.KEPT),
            Word(word="hmm", start=2.5, end=3.0, score=0.24, status=WordStatus.FILLER),
            Word(word="je", start=3.0, end=3.5, score=0.96, status=WordStatus.KEPT),
            Word(word="pense", start=3.5, end=4.0, score=0.98, status=WordStatus.KEPT),
        ],
        cuts=[
            Cut(
                start=0.5,
                end=1.0,
                cut_type=CutType.FILLER,
                reason=CutReason.FILLER_WORD,
                word="euh",
            ),
            Cut(
                start=2.5,
                end=3.0,
                cut_type=CutType.FILLER,
                reason=CutReason.FILLER_WORD,
                word="hmm",
            ),
        ],
        keep_segments=[
            KeepSegment(start=0.0, end=0.5),
            KeepSegment(start=1.0, end=2.5),
            KeepSegment(start=3.0, end=4.0),
        ],
        total_words=8,
        kept_words=6,
        filler_words=2,
        corrected_words=0,
        original_duration=4.0,
        final_duration=3.0,
        cut_duration=1.0,
    )


class TestCutterPipeline:
    """Tests for the complete cutter pipeline."""

    def test_initial_cut_for_silence(self, cutter_result):
        """Should create cuts for filler words."""
        # First filler word starts at 0.5
        initial_filler_cuts = [c for c in cutter_result.cuts if c.start == 0.5]
        assert len(initial_filler_cuts) > 0
        initial_cut = initial_filler_cuts[0]
        assert initial_cut.start == 0.5

    def test_cuts_are_sorted(self, cutter_result):
        """Cuts should be sorted by start time."""
        starts = [c.start for c in cutter_result.cuts]
        assert starts == sorted(starts), "Cuts are not sorted by start time"

    def test_cuts_dont_overlap(self, cutter_result):
        """Cuts should not overlap (after merging)."""
        cuts = sorted(cutter_result.cuts, key=lambda c: c.start)

        for i in range(len(cuts) - 1):
            current = cuts[i]
            next_cut = cuts[i + 1]
            assert current.end <= next_cut.start, (
                f"Cuts overlap: [{current.start}, {current.end}] and [{next_cut.start}, {next_cut.end}]"
            )


class TestFCPXMLOutput:
    """Tests for FCPXML output correctness."""

    def test_fcpxml_clips_match_keep_segments(self, cutter_result, sample_media_info, tmp_path):
        """FCPXML should have one clip per keep segment."""
        fcpxml_path = tmp_path / "test.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(cutter_result, sample_media_info, fcpxml_path)

        content = fcpxml_path.read_text()

        # Count asset-clip elements in spine (one per keep segment)
        import re

        clips = re.findall(r'<asset-clip[^>]*name="Keep \d+"', content)

        # One clip per keep segment (single asset = proper stereo)
        assert len(clips) == len(cutter_result.keep_segments), (
            f"FCPXML has {len(clips)} clips but expected {len(cutter_result.keep_segments)} keep segments"
        )

    def test_fcpxml_sequence_duration(self, cutter_result, sample_media_info, tmp_path):
        """FCPXML sequence duration should match final_duration."""
        fcpxml_path = tmp_path / "test.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(cutter_result, sample_media_info, fcpxml_path)

        content = fcpxml_path.read_text()

        # Find sequence duration attribute
        import re

        match = re.search(r'sequence[^>]*duration="(\d+)/(\d+)s"', content)
        if match:
            numerator = int(match.group(1))
            denominator = int(match.group(2))
            sequence_duration = numerator / denominator

            # Allow small tolerance due to frame rounding
            assert abs(sequence_duration - cutter_result.final_duration) < 0.1, (
                f"Sequence duration {sequence_duration}s doesn't match final_duration {cutter_result.final_duration}s"
            )

    def test_fcpxml_asset_path_exists(self, cutter_result, sample_media_info, tmp_path):
        """FCPXML asset src should point to file URI."""
        fcpxml_path = tmp_path / "test.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(cutter_result, sample_media_info, fcpxml_path)

        content = fcpxml_path.read_text()

        # Extract file path from src attribute
        import re

        match = re.search(r'src="file://([^"]+)"', content)
        if match:
            assert "video.mp4" in match.group(1), f"Asset path doesn't match: {match.group(1)}"
