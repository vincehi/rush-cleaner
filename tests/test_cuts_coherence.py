"""Tests for cut coherence and consistency.

These tests verify that:
1. Cuts don't overlap
2. Cuts have no negative duration
3. Cuts are sorted
4. Fillers are included in cuts
"""

import pytest

from src.config import CutterConfig
from src.models import Word, WordStatus, Cut, CutType, CutReason
from src.cutter import compute_cuts, merge_adjacent_cuts


class TestNoOverlappingCuts:
    """Tests to ensure cuts never overlap."""

    def test_cuts_dont_overlap_after_merge(self):
        """After merging, cuts should never overlap."""
        # Create overlapping cuts
        cuts = [
            Cut(start=0.0, end=2.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BEFORE_SPEECH),
            Cut(start=1.5, end=3.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD, word="euh"),
            Cut(start=4.0, end=5.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BETWEEN_SEGMENTS),
        ]

        merged = merge_adjacent_cuts(cuts)

        # Check no overlaps
        for i in range(len(merged) - 1):
            assert merged[i].end <= merged[i + 1].start, \
                f"Cuts overlap: [{merged[i].start}, {merged[i].end}] and [{merged[i + 1].start}, {merged[i + 1].end}]"

    def test_compute_cuts_produces_no_overlaps(self):
        """compute_cuts should produce non-overlapping cuts."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="um", start=0.5, end=0.7, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=0.7, end=1.0, score=0.9, status=WordStatus.KEPT),
            Word(word="euh", start=2.0, end=2.3, score=0.8, status=WordStatus.FILLER),
            Word(word="test", start=2.3, end=2.6, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=5.0)

        # Check no overlaps
        for i in range(len(cuts) - 1):
            assert cuts[i].end <= cuts[i + 1].start, \
                f"Cuts overlap: [{cuts[i].start}, {cuts[i].end}] and [{cuts[i + 1].start}, {cuts[i + 1].end}]"

    def test_adjacent_cuts_are_merged(self):
        """Adjacent cuts (end == start) should be merged."""
        cuts = [
            Cut(start=0.0, end=1.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BEFORE_SPEECH),
            Cut(start=1.0, end=2.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD),
        ]

        merged = merge_adjacent_cuts(cuts)

        # Should be a single cut
        assert len(merged) == 1
        assert merged[0].start == 0.0
        assert merged[0].end == 2.0


class TestNoNegativeDuration:
    """Tests to ensure cuts have positive duration."""

    def test_cuts_have_positive_duration(self):
        """Each cut must have end > start."""
        words = [
            Word(word="Hello", start=1.0, end=1.5, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=2.0)

        for cut in cuts:
            duration = cut.end - cut.start
            assert duration > 0, f"Cut has non-positive duration: [{cut.start}, {cut.end}]"

    def test_filler_cuts_have_positive_duration(self):
        """Filler cuts must have positive duration."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="um", start=0.5, end=0.7, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=0.7, end=1.0, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=2.0)

        filler_cuts = [c for c in cuts if c.cut_type == CutType.FILLER]
        for cut in filler_cuts:
            duration = cut.end - cut.start
            assert duration > 0, f"Filler cut has non-positive duration: [{cut.start}, {cut.end}]"


class TestCutsSorted:
    """Tests to ensure cuts are sorted by start time."""

    def test_cuts_are_sorted_by_start(self):
        """Cuts must be sorted by start time."""
        words = [
            Word(word="Hello", start=5.0, end=5.5, score=0.9, status=WordStatus.KEPT),
            Word(word="um", start=5.5, end=5.7, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=1.0, end=1.5, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=10.0)

        starts = [c.start for c in cuts]
        assert starts == sorted(starts), "Cuts are not sorted by start time"

    def test_merged_cuts_are_sorted(self):
        """Merged cuts must be sorted by start time."""
        # Unsorted input
        cuts = [
            Cut(start=5.0, end=6.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BETWEEN_SEGMENTS),
            Cut(start=0.0, end=1.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BEFORE_SPEECH),
            Cut(start=2.0, end=3.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD),
        ]

        merged = merge_adjacent_cuts(cuts)

        starts = [c.start for c in merged]
        assert starts == sorted(starts), "Merged cuts are not sorted by start time"


class TestFillersInCuts:
    """Tests to ensure fillers are included in cuts."""

    def test_filler_word_is_in_cut(self):
        """Each filler word must be covered by a cut."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="euh", start=0.5, end=0.7, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=0.7, end=1.0, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=2.0)

        filler = next(w for w in words if w.status == WordStatus.FILLER)

        # Check that filler is covered by at least one cut
        covered = any(
            cut.start <= filler.start and cut.end >= filler.end
            for cut in cuts
        )
        assert covered, f"Filler '{filler.word}' at [{filler.start}, {filler.end}] is not covered by any cut"

    def test_multiple_fillers_all_covered(self):
        """All filler words must be covered by cuts."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="um", start=0.5, end=0.7, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=0.7, end=1.0, score=0.9, status=WordStatus.KEPT),
            Word(word="euh", start=2.0, end=2.3, score=0.8, status=WordStatus.FILLER),
            Word(word="test", start=2.3, end=2.6, score=0.9, status=WordStatus.KEPT),
            Word(word="hmm", start=3.0, end=3.2, score=0.7, status=WordStatus.FILLER),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=5.0)

        filler_words = [w for w in words if w.status == WordStatus.FILLER]

        for filler in filler_words:
            covered = any(
                cut.start <= filler.start and cut.end >= filler.end
                for cut in cuts
            )
            assert covered, f"Filler '{filler.word}' at [{filler.start}, {filler.end}] is not covered"

    def test_sample_hmm_in_cut(self):
        """Test that 'hmm' from sample is in a cut."""
        words = [
            Word(word="test", start=4.268, end=4.588, score=0.888, status=WordStatus.KEPT),
            Word(word="hmm", start=8.642, end=8.702, score=0.241, status=WordStatus.FILLER),
            Word(word="je", start=8.742, end=8.883, score=0.967, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=16.815)

        hmm = next(w for w in words if w.word == "hmm")

        covered = any(
            cut.start <= hmm.start and cut.end >= hmm.end
            for cut in cuts
        )
        assert covered, "'hmm' should be covered by a cut"


class TestCutTypes:
    """Tests for cut type classification."""

    def test_silence_cut_type(self):
        """Silence cuts should have type SILENCE."""
        words = [
            Word(word="Hello", start=1.0, end=1.5, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig(min_silence=0.5)
        cuts = compute_cuts(words, config, total_duration=3.0)

        initial_cut = next((c for c in cuts if c.start == 0.0), None)
        assert initial_cut is not None
        assert initial_cut.cut_type == CutType.SILENCE

    def test_filler_cut_type(self):
        """Filler cuts should have type FILLER."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="euh", start=0.5, end=0.7, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=0.7, end=1.0, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=2.0)

        filler_cut = next((c for c in cuts if c.word == "euh"), None)
        assert filler_cut is not None
        assert filler_cut.cut_type == CutType.FILLER

    def test_mixed_cut_type_after_merge(self):
        """Merged cuts with different types should have type MIXED."""
        cuts = [
            Cut(start=0.0, end=1.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BEFORE_SPEECH),
            Cut(start=1.0, end=2.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD, word="euh"),
        ]

        merged = merge_adjacent_cuts(cuts)

        assert len(merged) == 1
        assert merged[0].cut_type == CutType.MIXED


class TestEdgeCases:
    """Tests for edge cases."""

    def test_no_words_entire_file_cut(self):
        """With no words, entire file should be one cut."""
        config = CutterConfig()
        cuts = compute_cuts([], config, total_duration=5.0)

        assert len(cuts) == 1
        assert cuts[0].start == 0.0
        assert cuts[0].end == 5.0
        assert cuts[0].cut_type == CutType.SILENCE

    def test_single_word_no_silence(self):
        """Single word at start with no surrounding silence should have minimal cuts."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig(min_silence=0.5)
        cuts = compute_cuts(words, config, total_duration=0.6)

        # Only end silence cut (0.1s is < min_silence, so no cut)
        # Actually end is 0.6 - 0.5 = 0.1s, which is < 0.5s min_silence
        # So there might be no cuts or just one small one
        # The key is no cuts at the beginning since word starts at 0.0
        initial_cut = next((c for c in cuts if c.start == 0.0), None)
        assert initial_cut is None, "Should not have initial cut when word starts at 0.0"

    def test_zero_duration_file(self):
        """Zero duration file should produce no cuts."""
        config = CutterConfig()
        cuts = compute_cuts([], config, total_duration=0.0)

        assert len(cuts) == 0
