"""Tests for silence_detector module."""

import pytest

from src.models import Segment, Word
from src.silence_detector import detect_silences


class TestDetectSilences:
    """Tests for detect_silences function."""

    def test_no_segments_with_duration(self):
        """Test detecting silence when no segments exist (entire file silent)."""
        result = detect_silences([], min_duration=0.5, total_duration=10.0)

        assert len(result) == 1
        assert result[0].start == 0.0
        assert result[0].end == 10.0
        assert result[0].cut_type == "silence"

    def test_no_segments_no_duration(self):
        """Test with no segments and no duration."""
        result = detect_silences([], min_duration=0.5, total_duration=0.0)
        assert len(result) == 0

    def test_silence_at_beginning(self):
        """Test detecting silence at the beginning."""
        segments = [
            Segment(start=2.0, end=5.0, text="Hello", words=[]),
            Segment(start=5.5, end=8.0, text="World", words=[]),
        ]

        result = detect_silences(segments, min_duration=0.5, total_duration=10.0)

        # Should find silence at beginning (0-2)
        beginning_silence = [c for c in result if c.start == 0.0]
        assert len(beginning_silence) == 1
        assert beginning_silence[0].end == 2.0

    def test_silence_between_segments(self):
        """Test detecting silence between segments."""
        segments = [
            Segment(start=0.0, end=2.0, text="Hello", words=[]),
            Segment(start=5.0, end=8.0, text="World", words=[]),  # 3s gap
        ]

        result = detect_silences(segments, min_duration=0.5, total_duration=10.0)

        # Should find silence between segments (2-5)
        middle_silence = [c for c in result if c.start == 2.0]
        assert len(middle_silence) == 1
        assert middle_silence[0].end == 5.0
        assert "3.0s" in middle_silence[0].label

    def test_silence_at_end(self):
        """Test detecting silence at the end."""
        segments = [
            Segment(start=0.0, end=2.0, text="Hello", words=[]),
            Segment(start=2.5, end=5.0, text="World", words=[]),
        ]

        result = detect_silences(segments, min_duration=0.5, total_duration=10.0)

        # Should find silence at end (5-10)
        end_silence = [c for c in result if c.end == 10.0]
        assert len(end_silence) == 1
        assert end_silence[0].start == 5.0

    def test_min_duration_filter(self):
        """Test that silences shorter than min_duration are filtered."""
        segments = [
            Segment(start=0.0, end=2.0, text="Hello", words=[]),
            Segment(start=2.2, end=4.0, text="World", words=[]),  # 0.2s gap - too short
        ]

        result = detect_silences(segments, min_duration=0.5, total_duration=10.0)

        # Should NOT find the 0.2s gap
        middle_silence = [c for c in result if c.start == 2.0]
        assert len(middle_silence) == 0

    def test_continuous_segments(self):
        """Test with continuous segments (no gaps)."""
        segments = [
            Segment(start=0.0, end=2.0, text="Hello", words=[]),
            Segment(start=2.0, end=4.0, text="World", words=[]),
            Segment(start=4.0, end=6.0, text="Test", words=[]),
        ]

        result = detect_silences(segments, min_duration=0.5, total_duration=6.0)

        # No silences should be detected
        assert len(result) == 0

    def test_all_silence_types(self):
        """Test detecting all types of silences in one file."""
        segments = [
            Segment(start=3.0, end=5.0, text="Hello", words=[]),
            Segment(start=7.0, end=9.0, text="World", words=[]),
        ]

        result = detect_silences(segments, min_duration=0.5, total_duration=15.0)

        # Should find 3 silences: beginning, middle, end
        assert len(result) == 3

        # Beginning
        assert result[0].start == 0.0
        assert result[0].end == 3.0

        # Middle
        assert result[1].start == 5.0
        assert result[1].end == 7.0

        # End
        assert result[2].start == 9.0
        assert result[2].end == 15.0
