"""Tests for keep segment coherence with V2 pipeline.

These tests verify that:
1. Keep segments don't overlap
2. Keep segments have no negative duration
3. Keep segments + cuts = total duration
4. No gaps between segments
"""

import json

import pytest

from derush.config import CutterConfig
from derush.cutter import run_pipeline
from derush.models import Cut, CutReason, CutType, KeepSegment, Word, WordStatus


class TestNoOverlappingSegments:
    """Tests to ensure keep segments never overlap."""

    def test_keep_segments_dont_overlap(self, tmp_path):
        """Keep segments should never overlap."""
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "start": 0.0, "end": 0.5, "score": 0.9},
                        {"word": "um", "start": 0.5, "end": 0.7, "score": 0.8},
                        {"word": "world", "start": 0.7, "end": 1.0, "score": 0.9},
                        {"word": "euh", "start": 2.0, "end": 2.3, "score": 0.8},
                        {"word": "test", "start": 2.3, "end": 2.6, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=5.0,
            language="en",
        )

        for i in range(len(result.keep_segments) - 1):
            assert result.keep_segments[i].end <= result.keep_segments[i + 1].start, (
                f"Segments overlap: [{result.keep_segments[i].start}, {result.keep_segments[i].end}] and [{result.keep_segments[i + 1].start}, {result.keep_segments[i + 1].end}]"
            )


class TestNoNegativeDuration:
    """Tests to ensure keep segments have positive duration."""

    def test_keep_segments_have_positive_duration(self, tmp_path):
        """Each keep segment must have end > start."""
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "start": 1.0, "end": 1.5, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=5.0,
            language="en",
        )

        for seg in result.keep_segments:
            duration = seg.end - seg.start
            assert duration > 0, f"Segment has non-positive duration: [{seg.start}, {seg.end}]"


class TestFullCoverage:
    """Tests to ensure keep_segments + cuts = total duration."""

    def test_full_coverage_with_cuts(self, tmp_path):
        """Keep segments + cuts should cover entire timeline."""
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "start": 1.0, "end": 1.5, "score": 0.9},
                        {"word": "um", "start": 1.5, "end": 1.7, "score": 0.8},
                        {"word": "world", "start": 1.7, "end": 2.0, "score": 0.9},
                    ],
                }
            )
        )

        total_duration = 5.0
        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=total_duration,
            language="en",
        )

        # Calculate total coverage
        cut_duration = sum(c.end - c.start for c in result.cuts)
        keep_duration = sum(s.duration for s in result.keep_segments)

        assert abs(cut_duration + keep_duration - total_duration) < 0.001, (
            f"Coverage gap: cuts={cut_duration}, keeps={keep_duration}, total={total_duration}"
        )

    def test_no_cuts_full_coverage(self, tmp_path):
        """With no cuts (all content), entire file should be keep segments."""
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "start": 0.0, "end": 5.0, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=5.0,
            language="en",
        )

        # Should have at least one keep segment
        assert len(result.keep_segments) >= 1


class TestNoGapsBetweenSegments:
    """Tests to ensure no gaps between keep segments and cuts."""

    def test_no_gaps_in_timeline(self, tmp_path):
        """Timeline should have no gaps between segments and cuts."""
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "start": 1.0, "end": 1.5, "score": 0.9},
                        {"word": "um", "start": 1.5, "end": 1.7, "score": 0.8},
                        {"word": "world", "start": 1.7, "end": 2.0, "score": 0.9},
                    ],
                }
            )
        )

        total_duration = 3.0
        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=total_duration,
            language="en",
        )

        # Combine all ranges and sort
        all_ranges = []
        for seg in result.keep_segments:
            all_ranges.append((seg.start, seg.end, "keep"))
        for cut in result.cuts:
            all_ranges.append((cut.start, cut.end, "cut"))

        all_ranges.sort(key=lambda x: x[0])

        # Check for gaps
        current_end = 0.0
        for start, end, _type in all_ranges:
            if start > current_end + 0.001:
                pytest.fail(f"Gap detected: [{current_end}, {start}] is not covered")
            current_end = max(current_end, end)

        # Check we reach the end
        assert abs(current_end - total_duration) < 0.001


class TestEdgeCases:
    """Tests for edge cases."""

    def test_no_words_no_segments(self, tmp_path):
        """With no words, no keep segments (entire file is cut)."""
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=5.0,
            language="en",
        )

        # No content words = no keep segments
        assert len(result.keep_segments) == 0

    def test_single_word(self, tmp_path):
        """Single word should produce one keep segment.

        Note: "hello" has 5 letters, so max duration is 0.35s (TIMING_5LETTER_MAX).
        If the raw duration (0.5s) exceeds max, it word is corrected to 0.35s.
        """
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "start": 0.0, "end": 0.5, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=2.0,
            language="en",
        )

        assert len(result.keep_segments) == 1
        assert result.keep_segments[0].start == 0.0
        # "hello" is corrected to 0.35s max (TIMING_5LETTER_MAX)
        assert result.keep_segments[0].end == 0.35
