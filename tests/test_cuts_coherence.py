"""Tests for cut coherence and consistency with V2 pipeline.

These tests verify that:
1. Cuts don't overlap
2. Cuts have no negative duration
3. Cuts are sorted
4. Fillers are included in cuts
"""

import json

from derush.cutter import run_pipeline
from derush.models import CutType, WordStatus


class TestNoOverlappingCuts:
    """Tests to ensure cuts never overlap."""

    def test_cuts_dont_overlap(self, tmp_path):
        """Cuts from pipeline should never overlap."""
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

        # Check no overlaps
        for i in range(len(result.cuts) - 1):
            assert result.cuts[i].end <= result.cuts[i + 1].start, (
                f"Cuts overlap: [{result.cuts[i].start}, {result.cuts[i].end}] and [{result.cuts[i + 1].start}, {result.cuts[i + 1].end}]"
            )


class TestNoNegativeDuration:
    """Tests to ensure cuts have positive duration."""

    def test_cuts_have_positive_duration(self, tmp_path):
        """Each cut must have end > start."""
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
            total_duration=2.0,
            language="en",
        )

        for cut in result.cuts:
            duration = cut.end - cut.start
            assert duration > 0, f"Cut has non-positive duration: [{cut.start}, {cut.end}]"


class TestCutsSorted:
    """Tests to ensure cuts are sorted by start time."""

    def test_cuts_are_sorted_by_start(self, tmp_path):
        """Cuts must be sorted by start time."""
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "start": 5.0, "end": 5.5, "score": 0.9},
                        {"word": "um", "start": 5.5, "end": 5.7, "score": 0.8},
                        {"word": "world", "start": 1.0, "end": 1.5, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=10.0,
            language="en",
        )

        starts = [c.start for c in result.cuts]
        assert starts == sorted(starts), "Cuts are not sorted by start time"


class TestFillersInCuts:
    """Tests to ensure fillers are included in cuts."""

    def test_filler_word_is_in_cut(self, tmp_path):
        """Each filler word must be covered by a cut."""
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "start": 0.0, "end": 0.5, "score": 0.9},
                        {"word": "euh", "start": 0.5, "end": 0.7, "score": 0.8},
                        {"word": "world", "start": 0.7, "end": 1.0, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=2.0,
            language="fr",
        )

        filler = next(w for w in result.words if w.status == WordStatus.FILLER)

        # Check that filler is covered by at least one cut
        covered = any(cut.start <= filler.start and cut.end >= filler.end for cut in result.cuts)
        assert covered, (
            f"Filler '{filler.word}' at [{filler.start}, {filler.end}] is not covered by any cut"
        )

    def test_multiple_fillers_all_covered(self, tmp_path):
        """All filler words must be covered by cuts."""
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
                        {"word": "hmm", "start": 3.0, "end": 3.2, "score": 0.7},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=5.0,
            language="en",
        )

        filler_words = [w for w in result.words if w.status == WordStatus.FILLER]

        for filler in filler_words:
            covered = any(cut.start <= filler.start and cut.end >= filler.end for cut in result.cuts)
            assert covered, (
                f"Filler '{filler.word}' at [{filler.start}, {filler.end}] is not covered"
            )


class TestEdgeCases:
    """Tests for edge cases."""

    def test_no_words_entire_file_cut(self, tmp_path):
        """With no words, entire file should be one cut."""
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

        assert len(result.cuts) == 1
        assert result.cuts[0].start == 0.0
        assert result.cuts[0].end == 5.0
        assert result.cuts[0].cut_type == CutType.SILENCE
