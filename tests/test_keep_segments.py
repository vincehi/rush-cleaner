"""Tests for keep segment coherence.

These tests verify that:
1. Keep segments don't overlap
2. Keep segments have no negative duration
3. Keep segments + cuts = total duration
4. No gaps between segments
"""

import pytest

from derush.config import CutterConfig
from derush.models import Word, WordStatus, Cut, CutType, CutReason, KeepSegment
from derush.cutter import compute_cuts, compute_keep_segments


class TestNoOverlappingSegments:
    """Tests to ensure keep segments never overlap."""

    def test_keep_segments_dont_overlap(self):
        """Keep segments should never overlap."""
        cuts = [
            Cut(start=0.0, end=1.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BEFORE_SPEECH),
            Cut(start=2.0, end=3.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD),
        ]

        segments = compute_keep_segments(cuts, total_duration=5.0)

        for i in range(len(segments) - 1):
            assert segments[i].end <= segments[i + 1].start, \
                f"Segments overlap: [{segments[i].start}, {segments[i].end}] and [{segments[i + 1].start}, {segments[i + 1].end}]"

    def test_keep_segments_from_pipeline_dont_overlap(self):
        """Keep segments from full pipeline should not overlap."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="um", start=0.5, end=0.7, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=0.7, end=1.0, score=0.9, status=WordStatus.KEPT),
            Word(word="euh", start=2.0, end=2.3, score=0.8, status=WordStatus.FILLER),
            Word(word="test", start=2.3, end=2.6, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=5.0)
        segments = compute_keep_segments(cuts, total_duration=5.0)

        for i in range(len(segments) - 1):
            assert segments[i].end <= segments[i + 1].start


class TestNoNegativeDuration:
    """Tests to ensure keep segments have positive duration."""

    def test_keep_segments_have_positive_duration(self):
        """Each keep segment must have end > start."""
        cuts = [
            Cut(start=1.0, end=2.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BETWEEN_SEGMENTS),
            Cut(start=3.0, end=4.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD),
        ]

        segments = compute_keep_segments(cuts, total_duration=5.0)

        for seg in segments:
            duration = seg.end - seg.start
            assert duration > 0, f"Segment has non-positive duration: [{seg.start}, {seg.end}]"

    def test_keep_segment_duration_property(self):
        """KeepSegment.duration property should return correct value."""
        segment = KeepSegment(start=1.0, end=2.5)

        assert segment.duration == 1.5


class TestFullCoverage:
    """Tests to ensure keep_segments + cuts = total duration."""

    def test_full_coverage_with_cuts(self):
        """Keep segments + cuts should cover entire timeline."""
        cuts = [
            Cut(start=0.0, end=1.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BEFORE_SPEECH),
            Cut(start=2.0, end=3.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD),
        ]

        total_duration = 5.0
        segments = compute_keep_segments(cuts, total_duration)

        # Calculate total coverage
        cut_duration = sum(c.end - c.start for c in cuts)
        keep_duration = sum(s.duration for s in segments)

        assert abs(cut_duration + keep_duration - total_duration) < 0.001, \
            f"Coverage gap: cuts={cut_duration}, keeps={keep_duration}, total={total_duration}"

    def test_full_coverage_from_pipeline(self):
        """Full pipeline should produce complete coverage."""
        words = [
            Word(word="Hello", start=1.0, end=1.5, score=0.9, status=WordStatus.KEPT),
            Word(word="um", start=1.5, end=1.7, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=1.7, end=2.0, score=0.9, status=WordStatus.KEPT),
        ]

        total_duration = 5.0
        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration)
        segments = compute_keep_segments(cuts, total_duration)

        # Calculate total coverage
        cut_duration = sum(c.end - c.start for c in cuts)
        keep_duration = sum(s.duration for s in segments)

        assert abs(cut_duration + keep_duration - total_duration) < 0.001

    def test_no_cuts_full_coverage(self):
        """With no cuts, entire file should be one keep segment."""
        total_duration = 5.0
        segments = compute_keep_segments([], total_duration)

        assert len(segments) == 1
        assert segments[0].start == 0.0
        assert segments[0].end == total_duration


class TestNoGapsBetweenSegments:
    """Tests to ensure no gaps between keep segments and cuts."""

    def test_no_gaps_in_timeline(self):
        """Timeline should have no gaps between segments and cuts."""
        cuts = [
            Cut(start=0.0, end=1.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BEFORE_SPEECH),
            Cut(start=2.0, end=3.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD),
            Cut(start=4.0, end=5.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_AFTER_SPEECH),
        ]

        total_duration = 5.0
        segments = compute_keep_segments(cuts, total_duration)

        # Combine all ranges and sort
        all_ranges = []
        for seg in segments:
            all_ranges.append((seg.start, seg.end, "keep"))
        for cut in cuts:
            all_ranges.append((cut.start, cut.end, "cut"))

        all_ranges.sort(key=lambda x: x[0])

        # Check for gaps
        current_end = 0.0
        for start, end, type_ in all_ranges:
            if start > current_end + 0.001:
                pytest.fail(f"Gap detected: [{current_end}, {start}] is not covered")
            current_end = max(current_end, end)

        # Check we reach the end
        assert abs(current_end - total_duration) < 0.001

    def test_adjacent_segments_and_cuts(self):
        """Segments should be adjacent to cuts (no micro-gaps)."""
        words = [
            Word(word="Hello", start=1.0, end=1.5, score=0.9, status=WordStatus.KEPT),
            Word(word="um", start=1.5, end=1.7, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=1.7, end=2.0, score=0.9, status=WordStatus.KEPT),
        ]

        total_duration = 3.0
        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration)
        segments = compute_keep_segments(cuts, total_duration)

        # Build timeline and check adjacency
        timeline = []
        for seg in segments:
            timeline.append(("keep", seg.start, seg.end))
        for cut in cuts:
            timeline.append(("cut", cut.start, cut.end))

        timeline.sort(key=lambda x: x[1])

        for i in range(len(timeline) - 1):
            current_end = timeline[i][2]
            next_start = timeline[i + 1][1]
            assert abs(current_end - next_start) < 0.001, \
                f"Gap between {timeline[i]} and {timeline[i + 1]}"


class TestSampleData:
    """Tests using sample.mov data patterns."""

    def test_sample_keep_segments_count(self):
        """Sample should produce 4 keep segments."""
        # Simulating the sample data pattern
        words = [
            Word(word="petite", start=1.6, end=2.543, score=0.806, status=WordStatus.KEPT),
            Word(word="démo", start=2.583, end=3.606, score=0.625, status=WordStatus.KEPT),
            Word(word="de", start=3.646, end=4.208, score=0.984, status=WordStatus.KEPT),
            Word(word="test", start=4.268, end=4.588, score=0.888, status=WordStatus.KEPT),
            Word(word="hmm", start=8.642, end=8.702, score=0.241, status=WordStatus.FILLER),
            Word(word="je", start=8.742, end=8.883, score=0.967, status=WordStatus.KEPT),
            Word(word="pense", start=8.923, end=9.284, score=0.981, status=WordStatus.KEPT),
            Word(word="que", start=9.324, end=9.524, score=0.844, status=WordStatus.KEPT),
            Word(word="voilà", start=12.153, end=12.775, score=0.829, status=WordStatus.KEPT),
            Word(word="de", start=14.999, end=15.186, score=0.814, status=WordStatus.KEPT),
            Word(word="quoi", start=15.227, end=15.414, score=0.944, status=WordStatus.KEPT),
            Word(word="par", start=15.455, end=15.58, score=0.784, status=WordStatus.KEPT),
            Word(word="le", start=15.6, end=15.704, score=0.81, status=WordStatus.KEPT),
            Word(word="ton", start=15.725, end=16.741, score=0.884, status=WordStatus.KEPT),
        ]

        total_duration = 16.814739
        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration)
        segments = compute_keep_segments(cuts, total_duration)

        # Should have 4 keep segments
        assert len(segments) == 4, f"Expected 4 segments, got {len(segments)}"

    def test_sample_keep_segment_timestamps(self):
        """Test specific keep segment timestamps from sample."""
        words = [
            Word(word="petite", start=1.6, end=2.543, score=0.806, status=WordStatus.KEPT),
            Word(word="démo", start=2.583, end=3.606, score=0.625, status=WordStatus.KEPT),
            Word(word="de", start=3.646, end=4.208, score=0.984, status=WordStatus.KEPT),
            Word(word="test", start=4.268, end=4.588, score=0.888, status=WordStatus.KEPT),
            Word(word="hmm", start=8.642, end=8.702, score=0.241, status=WordStatus.FILLER),
            Word(word="je", start=8.742, end=8.883, score=0.967, status=WordStatus.KEPT),
            Word(word="pense", start=8.923, end=9.284, score=0.981, status=WordStatus.KEPT),
            Word(word="que", start=9.324, end=9.524, score=0.844, status=WordStatus.KEPT),
            Word(word="voilà", start=12.153, end=12.775, score=0.829, status=WordStatus.KEPT),
            Word(word="de", start=14.999, end=15.186, score=0.814, status=WordStatus.KEPT),
            Word(word="quoi", start=15.227, end=15.414, score=0.944, status=WordStatus.KEPT),
            Word(word="par", start=15.455, end=15.58, score=0.784, status=WordStatus.KEPT),
            Word(word="le", start=15.6, end=15.704, score=0.81, status=WordStatus.KEPT),
            Word(word="ton", start=15.725, end=16.741, score=0.884, status=WordStatus.KEPT),
        ]

        total_duration = 16.814739
        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration)
        segments = compute_keep_segments(cuts, total_duration)

        # Keep 1: 1.6 → 4.588s (contains "petite démo de test")
        assert segments[0].start == pytest.approx(1.6, abs=0.01)
        assert segments[0].end == pytest.approx(4.588, abs=0.01)

        # Keep 2: 8.742 → 9.524s (contains "je pense que")
        assert segments[1].start == pytest.approx(8.742, abs=0.01)
        assert segments[1].end == pytest.approx(9.524, abs=0.01)

        # Keep 3: 12.153 → 12.775s (contains "voilà")
        assert segments[2].start == pytest.approx(12.153, abs=0.01)
        assert segments[2].end == pytest.approx(12.775, abs=0.01)

        # Keep 4: 14.999 → end (contains "de quoi par le ton")
        assert segments[3].start == pytest.approx(14.999, abs=0.01)
        assert segments[3].end == pytest.approx(16.814739, abs=0.01)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_no_cuts_single_segment(self):
        """With no cuts, should have one segment covering entire duration."""
        segments = compute_keep_segments([], total_duration=10.0)

        assert len(segments) == 1
        assert segments[0].start == 0.0
        assert segments[0].end == 10.0

    def test_cut_at_start(self):
        """Cut at start should result in segment starting after cut."""
        cuts = [
            Cut(start=0.0, end=2.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BEFORE_SPEECH),
        ]

        segments = compute_keep_segments(cuts, total_duration=5.0)

        assert len(segments) == 1
        assert segments[0].start == 2.0
        assert segments[0].end == 5.0

    def test_cut_at_end(self):
        """Cut at end should result in segment ending before cut."""
        cuts = [
            Cut(start=3.0, end=5.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_AFTER_SPEECH),
        ]

        segments = compute_keep_segments(cuts, total_duration=5.0)

        assert len(segments) == 1
        assert segments[0].start == 0.0
        assert segments[0].end == 3.0

    def test_zero_duration_file(self):
        """Zero duration file should produce no segments."""
        segments = compute_keep_segments([], total_duration=0.0)

        assert len(segments) == 0

    def test_consecutive_cuts(self):
        """Consecutive cuts should result in proper segments."""
        cuts = [
            Cut(start=0.0, end=1.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BEFORE_SPEECH),
            Cut(start=1.0, end=2.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD),
            Cut(start=2.0, end=3.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BETWEEN_SEGMENTS),
        ]

        segments = compute_keep_segments(cuts, total_duration=5.0)

        # Should have one segment from 3.0 to 5.0
        assert len(segments) == 1
        assert segments[0].start == 3.0
        assert segments[0].end == 5.0
