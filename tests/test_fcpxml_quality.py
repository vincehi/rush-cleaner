"""Tests for FCPXML export quality.

These tests verify that:
1. No micro-discontinuities between clips
2. True framerate is used (not hardcoded)
3. Sequence duration is coherent
"""

import re
from pathlib import Path

import pytest
from lxml import etree

from src.config import CutterConfig
from src.exporters.fcpxml import FCPXMLExporter
from src.models import (
    Cut,
    CutterResult,
    CutReason,
    CutType,
    KeepSegment,
    MediaInfo,
    Word,
    WordStatus,
)


def parse_rational(time_str: str) -> tuple[int, int]:
    """Parse rational time string (num/den)s to numerator and denominator."""
    value = time_str.rstrip("s")
    num, den = map(int, value.split("/"))
    return num, den


class TestNoMicroDiscontinuities:
    """Tests to ensure no micro-discontinuities between clips."""

    def test_no_gaps_between_clips(self, tmp_path):
        """Each clip's offset + duration should equal next clip's offset."""
        media_info = MediaInfo(
            fps=25.0,
            fps_rational="25/1",
            duration=10.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        result = CutterResult(
            words=[],
            cuts=[],
            keep_segments=[
                KeepSegment(start=0.0, end=2.0),
                KeepSegment(start=2.0, end=4.0),
                KeepSegment(start=4.0, end=7.0),
                KeepSegment(start=7.0, end=10.0),
            ],
            total_words=0,
            kept_words=0,
            filler_words=0,
            original_duration=10.0,
            final_duration=10.0,
            cut_duration=0.0,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        asset_clips = tree.xpath("//asset-clip")

        # Check that each clip's offset + duration equals next clip's offset
        for i in range(len(asset_clips) - 1):
            current = asset_clips[i]
            next_clip = asset_clips[i + 1]

            offset_num, offset_den = parse_rational(current.get("offset"))
            dur_num, dur_den = parse_rational(current.get("duration"))
            next_offset_num, next_offset_den = parse_rational(next_clip.get("offset"))

            # Calculate end position: offset + duration
            # Using common denominator
            end_num = offset_num * dur_den + dur_num * offset_den
            end_den = offset_den * dur_den

            # Cross-multiply to compare
            expected = end_num * next_offset_den
            actual = next_offset_num * end_den

            assert expected == actual, \
                f"Discontinuity between clip {i+1} and {i+2}: " \
                f"{current.get('offset')} + {current.get('duration')} != {next_clip.get('offset')}"

    def test_no_gaps_with_cuts(self, tmp_path):
        """No gaps should appear even when there are cuts between segments."""
        media_info = MediaInfo(
            fps=25.0,
            fps_rational="25/1",
            duration=10.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        # Segments with gaps (cuts) between them
        result = CutterResult(
            words=[],
            cuts=[
                Cut(start=2.0, end=3.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD),
                Cut(start=5.0, end=6.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BETWEEN_SEGMENTS),
            ],
            keep_segments=[
                KeepSegment(start=0.0, end=2.0),   # 2s
                KeepSegment(start=3.0, end=5.0),   # 2s
                KeepSegment(start=6.0, end=10.0),  # 4s
            ],
            total_words=0,
            kept_words=0,
            filler_words=0,
            original_duration=10.0,
            final_duration=8.0,
            cut_duration=2.0,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        asset_clips = tree.xpath("//asset-clip")

        # Check continuity
        for i in range(len(asset_clips) - 1):
            current = asset_clips[i]
            next_clip = asset_clips[i + 1]

            offset_num, offset_den = parse_rational(current.get("offset"))
            dur_num, dur_den = parse_rational(current.get("duration"))
            next_offset_num, next_offset_den = parse_rational(next_clip.get("offset"))

            end_num = offset_num * dur_den + dur_num * offset_den
            end_den = offset_den * dur_den

            expected = end_num * next_offset_den
            actual = next_offset_num * end_den

            assert expected == actual

    def test_sample_no_discontinuities(self, tmp_path):
        """Test no discontinuities with sample-like data."""
        # Using sample.mov frame rate
        media_info = MediaInfo(
            fps=28.306403351286654,
            fps_rational="47300/1671",
            duration=16.814739,
            width=1620,
            height=1080,
            has_video=True,
            file_path="/path/to/sample.mov"
        )

        # Sample keep segments
        result = CutterResult(
            words=[],
            cuts=[],
            keep_segments=[
                KeepSegment(start=1.6, end=4.588),
                KeepSegment(start=8.742, end=9.524),
                KeepSegment(start=12.153, end=12.775),
                KeepSegment(start=14.999, end=16.814739),
            ],
            total_words=14,
            kept_words=13,
            filler_words=1,
            original_duration=16.814739,
            final_duration=6.208,
            cut_duration=10.607,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        asset_clips = tree.xpath("//asset-clip")

        # Check continuity for all 4 clips
        for i in range(len(asset_clips) - 1):
            current = asset_clips[i]
            next_clip = asset_clips[i + 1]

            offset_num, offset_den = parse_rational(current.get("offset"))
            dur_num, dur_den = parse_rational(current.get("duration"))
            next_offset_num, next_offset_den = parse_rational(next_clip.get("offset"))

            end_num = offset_num * dur_den + dur_num * offset_den
            end_den = offset_den * dur_den

            expected = end_num * next_offset_den
            actual = next_offset_num * end_den

            assert expected == actual, \
                f"Discontinuity at clip {i+1}: expected {expected}, got {actual}"


class TestTrueFramerate:
    """Tests to ensure true framerate is used, not hardcoded."""

    def test_uses_fps_rational_not_hardcoded(self, tmp_path):
        """FCPXML should use fps_rational, not hardcoded 60000."""
        media_info = MediaInfo(
            fps=28.306403351286654,
            fps_rational="47300/1671",  # Unusual framerate
            duration=10.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        result = CutterResult(
            words=[],
            cuts=[],
            keep_segments=[KeepSegment(start=0.0, end=10.0)],
            total_words=0,
            kept_words=0,
            filler_words=0,
            original_duration=10.0,
            final_duration=10.0,
            cut_duration=0.0,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        content = output_path.read_text()

        # Should contain the actual framerate, not 60000
        assert "47300" in content, "Should use fps_rational numerator"
        assert "1671" in content, "Should use fps_rational denominator"
        assert "60000" not in content, "Should not contain hardcoded 60000"

    def test_format_frame_duration_correct(self, tmp_path):
        """Format frameDuration should be inverted from fps_rational."""
        media_info = MediaInfo(
            fps=28.306403351286654,
            fps_rational="47300/1671",
            duration=10.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        result = CutterResult(
            words=[],
            cuts=[],
            keep_segments=[KeepSegment(start=0.0, end=10.0)],
            total_words=0,
            kept_words=0,
            filler_words=0,
            original_duration=10.0,
            final_duration=10.0,
            cut_duration=0.0,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        format_el = tree.xpath("//format")[0]
        frame_duration = format_el.get("frameDuration")

        # frameDuration should be inverted: 1671/47300s (not 47300/1671s)
        assert frame_duration == "1671/47300s", \
            f"Expected '1671/47300s', got '{frame_duration}'"

    def test_standard_25fps(self, tmp_path):
        """Test with standard 25fps."""
        media_info = MediaInfo(
            fps=25.0,
            fps_rational="25/1",
            duration=10.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        result = CutterResult(
            words=[],
            cuts=[],
            keep_segments=[KeepSegment(start=0.0, end=10.0)],
            total_words=0,
            kept_words=0,
            filler_words=0,
            original_duration=10.0,
            final_duration=10.0,
            cut_duration=0.0,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        format_el = tree.xpath("//format")[0]
        frame_duration = format_el.get("frameDuration")

        assert frame_duration == "1/25s"

    def test_2997_fps(self, tmp_path):
        """Test with 29.97fps (drop-frame)."""
        media_info = MediaInfo(
            fps=29.97,
            fps_rational="30000/1001",
            duration=10.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        result = CutterResult(
            words=[],
            cuts=[],
            keep_segments=[KeepSegment(start=0.0, end=10.0)],
            total_words=0,
            kept_words=0,
            filler_words=0,
            original_duration=10.0,
            final_duration=10.0,
            cut_duration=0.0,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        format_el = tree.xpath("//format")[0]
        frame_duration = format_el.get("frameDuration")

        # frameDuration should be 1001/30000s
        assert frame_duration == "1001/30000s"


class TestSequenceDurationCoherence:
    """Tests to ensure sequence duration matches sum of clips."""

    def test_sequence_duration_equals_sum_of_clips(self, tmp_path):
        """Sequence duration should equal the sum of all clip durations."""
        media_info = MediaInfo(
            fps=25.0,
            fps_rational="25/1",
            duration=10.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        result = CutterResult(
            words=[],
            cuts=[
                Cut(start=2.0, end=3.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD),
            ],
            keep_segments=[
                KeepSegment(start=0.0, end=2.0),   # 2s
                KeepSegment(start=3.0, end=10.0),  # 7s
            ],
            total_words=0,
            kept_words=0,
            filler_words=0,
            original_duration=10.0,
            final_duration=9.0,
            cut_duration=1.0,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        sequence = tree.xpath("//sequence")[0]
        asset_clips = tree.xpath("//asset-clip")

        # Get sequence duration
        seq_duration_str = sequence.get("duration")
        seq_num, seq_den = parse_rational(seq_duration_str)

        # Calculate sum of clip durations
        total_frames = 0
        for clip in asset_clips:
            dur_num, dur_den = parse_rational(clip.get("duration"))
            # Convert to common denominator (fps_num)
            frames = dur_num * media_info.fps // dur_den
            total_frames += frames

        # Convert sequence duration to frames
        fps_num, fps_den = map(int, media_info.fps_rational.split("/"))
        seq_frames = seq_num * fps_num // seq_den

        assert seq_frames == total_frames, \
            f"Sequence duration ({seq_frames} frames) != sum of clips ({total_frames} frames)"

    def test_sequence_duration_matches_final_duration(self, tmp_path):
        """Sequence duration should match final_duration from result."""
        media_info = MediaInfo(
            fps=25.0,
            fps_rational="25/1",
            duration=16.815,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        # Sample-like data
        result = CutterResult(
            words=[],
            cuts=[],
            keep_segments=[
                KeepSegment(start=1.6, end=4.588),
                KeepSegment(start=8.742, end=9.524),
                KeepSegment(start=12.153, end=12.775),
                KeepSegment(start=14.999, end=16.815),
            ],
            total_words=14,
            kept_words=13,
            filler_words=1,
            original_duration=16.815,
            final_duration=6.208,
            cut_duration=10.607,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        sequence = tree.xpath("//sequence")[0]
        seq_duration_str = sequence.get("duration")

        # Parse sequence duration
        seq_num, seq_den = parse_rational(seq_duration_str)
        seq_seconds = seq_num / seq_den

        # Should be close to final_duration (allowing for frame rounding)
        assert abs(seq_seconds - result.final_duration) < 0.1, \
            f"Sequence duration ({seq_seconds}s) != final_duration ({result.final_duration}s)"


class TestClipAttributes:
    """Tests for clip attribute correctness."""

    def test_first_clip_offset_zero(self, tmp_path):
        """First clip should have offset 0."""
        media_info = MediaInfo(
            fps=25.0,
            fps_rational="25/1",
            duration=10.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        result = CutterResult(
            words=[],
            cuts=[],
            keep_segments=[
                KeepSegment(start=1.0, end=3.0),
                KeepSegment(start=5.0, end=8.0),
            ],
            total_words=0,
            kept_words=0,
            filler_words=0,
            original_duration=10.0,
            final_duration=5.0,
            cut_duration=5.0,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        first_clip = tree.xpath("//asset-clip")[0]

        assert first_clip.get("offset") == "0/25s", \
            f"First clip offset should be 0, got {first_clip.get('offset')}"

    def test_clip_start_matches_segment_start(self, tmp_path):
        """Clip 'start' attribute should match original segment start in source."""
        media_info = MediaInfo(
            fps=25.0,
            fps_rational="25/1",
            duration=10.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        result = CutterResult(
            words=[],
            cuts=[],
            keep_segments=[
                KeepSegment(start=1.5, end=3.5),  # Starts at 1.5s in source
            ],
            total_words=0,
            kept_words=0,
            filler_words=0,
            original_duration=10.0,
            final_duration=2.0,
            cut_duration=8.0,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        clip = tree.xpath("//asset-clip")[0]

        # Start should be 1.5s = 37.5 frames ≈ 38 frames at 25fps
        # In rational: 38/25s
        start_str = clip.get("start")
        start_num, start_den = parse_rational(start_str)
        start_seconds = start_num / start_den

        assert abs(start_seconds - 1.5) < 0.05, \
            f"Clip start ({start_seconds}s) should match segment start (1.5s)"

    def test_clip_names_are_numbered(self, tmp_path):
        """Clips should be named 'Keep 1', 'Keep 2', etc."""
        media_info = MediaInfo(
            fps=25.0,
            fps_rational="25/1",
            duration=10.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        result = CutterResult(
            words=[],
            cuts=[],
            keep_segments=[
                KeepSegment(start=0.0, end=2.0),
                KeepSegment(start=3.0, end=5.0),
                KeepSegment(start=6.0, end=8.0),
            ],
            total_words=0,
            kept_words=0,
            filler_words=0,
            original_duration=10.0,
            final_duration=6.0,
            cut_duration=4.0,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        asset_clips = tree.xpath("//asset-clip")

        expected_names = ["Keep 1", "Keep 2", "Keep 3"]
        for clip, expected in zip(asset_clips, expected_names):
            assert clip.get("name") == expected, \
                f"Expected clip name '{expected}', got '{clip.get('name')}'"


class TestAntiRegression:
    """Anti-regression tests for FCPXML export."""

    def test_no_floating_point_accumulation(self, tmp_path):
        """REGRESSION: No floating-point accumulation errors in timeline."""
        # Use a duration that could cause floating-point issues
        media_info = MediaInfo(
            fps=29.97,
            fps_rational="30000/1001",
            duration=100.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
        )

        # Many small segments
        segments = []
        for i in range(20):
            segments.append(KeepSegment(start=i * 4.5, end=i * 4.5 + 2.5))

        result = CutterResult(
            words=[],
            cuts=[],
            keep_segments=segments,
            total_words=0,
            kept_words=0,
            filler_words=0,
            original_duration=100.0,
            final_duration=50.0,
            cut_duration=50.0,
        )

        output_path = tmp_path / "test.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        asset_clips = tree.xpath("//asset-clip")

        # Check that all clips are contiguous
        for i in range(len(asset_clips) - 1):
            current = asset_clips[i]
            next_clip = asset_clips[i + 1]

            offset_num, offset_den = parse_rational(current.get("offset"))
            dur_num, dur_den = parse_rational(current.get("duration"))
            next_offset_num, next_offset_den = parse_rational(next_clip.get("offset"))

            # Exact comparison - no floating-point errors
            end_num = offset_num * dur_den + dur_num * offset_den
            end_den = offset_den * dur_den

            expected = end_num * next_offset_den
            actual = next_offset_num * end_den

            assert expected == actual, \
                f"Floating-point error at clip {i+1}: {expected} != {actual}"
