"""Tests for robustness and edge cases with V2 pipeline.

These tests verify that:
1. Silent audio files are handled correctly
2. Continuous speech files are handled correctly
3. Abnormally long words are corrected
4. Empty inputs are handled gracefully
"""

import json

import pytest

from derush.config import CutterConfig
from derush.cutter import (
    classify_words,
    correct_word_timestamps,
    run_pipeline,
)
from derush.models import Word, WordStatus


class TestSilentFile:
    """Tests for files with no speech (silent audio)."""

    def test_empty_whisperx_data(self, tmp_path):
        """Empty WhisperX data should be handled gracefully."""
        whisperx_path = tmp_path / "empty.json"
        whisperx_path.write_text(
            json.dumps({"segments": [], "word_segments": [], "language": "fr"})
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=30.0,
            language="fr",
        )

        assert result.total_words == 0
        assert result.kept_words == 0
        assert result.filler_words == 0
        assert len(result.cuts) == 1
        assert result.cuts[0].start == 0.0
        assert result.cuts[0].end == 30.0

    def test_no_words_single_cut(self, tmp_path):
        """A file with no words should have one cut covering entire duration."""
        whisperx_path = tmp_path / "empty.json"
        whisperx_path.write_text(json.dumps({"word_segments": []}))

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=30.0,
            language="en",
        )

        assert len(result.cuts) == 1
        assert result.cuts[0].start == 0.0
        assert result.cuts[0].end == 30.0


class TestContinuousSpeech:
    """Tests for files with continuous speech (no silences)."""

    def test_continuous_speech_single_segment(self, tmp_path):
        """A file with continuous speech should have one keep segment."""
        whisperx_path = tmp_path / "continuous.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "Hello", "start": 0.0, "end": 0.5, "score": 0.9},
                        {"word": "world", "start": 0.5, "end": 1.0, "score": 0.9},
                        {"word": "this", "start": 1.0, "end": 1.3, "score": 0.9},
                        {"word": "is", "start": 1.3, "end": 1.5, "score": 0.9},
                        {"word": "continuous", "start": 1.5, "end": 2.0, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=2.5,
            language="en",
        )

        # Should have one keep segment (all words merged)
        assert len(result.keep_segments) >= 1

    def test_continuous_speech_no_filler_cuts(self, tmp_path):
        """Continuous speech without fillers should have no filler cuts."""
        whisperx_path = tmp_path / "no_fillers.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "Je", "start": 0.0, "end": 0.2, "score": 0.9},
                        {"word": "parle", "start": 0.2, "end": 0.5, "score": 0.9},
                        {"word": "continuellement", "start": 0.5, "end": 1.0, "score": 0.9},
                        {"word": "sans", "start": 1.0, "end": 1.2, "score": 0.9},
                        {"word": "pause", "start": 1.2, "end": 1.5, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=2.0,
            language="fr",
        )

        filler_cuts = [c for c in result.cuts if c.cut_type.value == "filler"]
        assert len(filler_cuts) == 0


class TestAbnormallyLongWords:
    """Tests for handling abnormally long words from WhisperX."""

    def test_10_second_word_is_corrected(self):
        """A 10-second word should be corrected to reasonable duration."""
        words = [
            Word(word="test", start=0.0, end=10.0, score=0.9),
        ]

        corrected, count = correct_word_timestamps(words)

        duration = corrected[0].end - corrected[0].start
        assert duration < 0.5, f"Word should be corrected to <0.5s, got {duration}s"
        assert count == 1

    def test_30_second_word_is_corrected(self):
        """Even a 30-second word should be corrected."""
        words = [
            Word(word="bonjour", start=0.0, end=30.0, score=0.8),
        ]

        corrected, count = correct_word_timestamps(words)

        duration = corrected[0].end - corrected[0].start
        assert duration < 1.0
        assert count == 1

    def test_long_word_exposes_hidden_gap(self):
        """Correcting a long word should expose hidden gaps."""
        # "test" absorbs a large gap
        words = [
            Word(word="de", start=0.0, end=0.3, score=0.9),
            Word(word="test", start=0.3, end=8.0, score=0.8),  # 7.7s - way too long!
            Word(word="suite", start=8.0, end=8.5, score=0.9),
        ]

        corrected, count = correct_word_timestamps(words)

        # After correction, "test" should be much shorter
        test_word = corrected[1]
        test_duration = test_word.end - test_word.start
        assert test_duration < 1.0

        # Gap between corrected "test" and "suite" should be exposed
        gap = corrected[2].start - test_word.end
        assert gap > 5.0, "Hidden gap should be exposed after correction"


class TestVeryShortFiles:
    """Tests for very short files."""

    def test_1_second_file(self, tmp_path):
        """A 1-second file should be handled correctly."""
        whisperx_path = tmp_path / "short.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "Hi", "start": 0.0, "end": 0.5, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=1.0,
            language="en",
        )

        # Should handle gracefully
        assert len(result.keep_segments) >= 1

    def test_500ms_file(self, tmp_path):
        """A 500ms file should be handled correctly."""
        whisperx_path = tmp_path / "tiny.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "ok", "start": 0.0, "end": 0.3, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=0.5,
            language="en",
        )

        # Should handle gracefully
        assert len(result.keep_segments) >= 1


class TestBoundaryConditions:
    """Tests for boundary conditions."""

    def test_word_at_exact_start(self, tmp_path):
        """Word starting exactly at 0.0 should not cause issues."""
        whisperx_path = tmp_path / "start.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "Start", "start": 0.0, "end": 0.5, "score": 0.9},
                        {"word": "middle", "start": 0.5, "end": 1.0, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=2.0,
            language="en",
        )

        # No cut at start since word starts at 0.0
        initial_cut = next((c for c in result.cuts if c.start == 0.0), None)
        assert initial_cut is None

    def test_word_at_exact_end(self, tmp_path):
        """Word ending exactly at duration should not cause issues."""
        whisperx_path = tmp_path / "end.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "End", "start": 1.5, "end": 2.0, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=2.0,
            language="en",
        )

        # Should not crash and produce valid output
        assert len(result.keep_segments) >= 1

    def test_zero_duration_word(self):
        """Word with zero duration should be handled."""
        words = [
            Word(word="zero", start=1.0, end=1.0, score=0.9),
        ]

        corrected, count = correct_word_timestamps(words)

        # Word has 0s duration and is not > max_word_duration, so no correction
        assert corrected[0].end == corrected[0].start  # 0 duration preserved
        assert count == 0

    def test_overlapping_words(self, tmp_path):
        """Overlapping words should be handled gracefully."""
        whisperx_path = tmp_path / "overlap.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "first", "start": 0.0, "end": 1.0, "score": 0.9},
                        {"word": "overlap", "start": 0.8, "end": 1.5, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=2.0,
            language="en",
        )

        # Should produce valid output
        assert len(result.keep_segments) >= 1


class TestUnusualInputs:
    """Tests for unusual or malformed inputs."""

    def test_single_filler_word(self, tmp_path):
        """A file with only a filler word should have no keep segments."""
        whisperx_path = tmp_path / "filler_only.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "euh", "start": 0.0, "end": 0.3, "score": 0.8},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=1.0,
            language="fr",
        )

        # All words are fillers, so no keep segments
        assert result.kept_words == 0
        assert result.filler_words == 1

    def test_all_filler_words(self, tmp_path):
        """A file with only filler words should have no keep segments."""
        whisperx_path = tmp_path / "all_fillers.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "euh", "start": 1.0, "end": 1.3, "score": 0.8},
                        {"word": "um", "start": 3.0, "end": 3.2, "score": 0.7},
                        {"word": "hmm", "start": 5.0, "end": 5.2, "score": 0.6},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=10.0,
            language="en",
        )

        # All fillers should be detected
        assert result.filler_words == 3
        assert result.kept_words == 0

    def test_very_low_scores(self):
        """Words with very low scores but normal duration should not be corrected."""
        words = [
            Word(word="unclear", start=0.0, end=0.5, score=0.1),  # Very low score, normal duration
            Word(word="also", start=0.5, end=0.9, score=0.05),  # Even lower score, normal duration
        ]

        corrected, count = correct_word_timestamps(words)

        # Words with normal duration should not be corrected, regardless of score
        assert corrected[0].end - corrected[0].start == pytest.approx(0.5, abs=0.01)
        assert corrected[1].end - corrected[1].start == pytest.approx(0.4, abs=0.01)
        assert count == 0

    def test_special_characters_in_words(self):
        """Words with special characters should be handled."""
        words = [
            Word(word="café", start=0.0, end=0.5, score=0.9),
            Word(word="naïve", start=0.5, end=1.0, score=0.9),
            Word(word="test!", start=1.0, end=1.5, score=0.9),
        ]

        result = classify_words(words, language="fr")

        # All should be kept (not fillers)
        assert all(w.status == WordStatus.KEPT for w in result)
