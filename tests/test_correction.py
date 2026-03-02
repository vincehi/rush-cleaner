"""Tests for word timestamp correction.

These tests verify that:
1. Words exceeding their expected duration (based on length) are corrected
2. Correction exposes hidden gaps for proper detection
"""

import pytest

from derush.config import CutterConfig
from derush.cutter import correct_word_timestamps
from derush.models import Word, WordStatus


class TestDurationBasedCorrection:
    """Tests for duration-based word correction (based on word length)."""

    def test_word_exceeding_expected_duration_is_corrected(self):
        """A word exceeding its expected duration must be corrected."""
        # "test" with 4.354s duration (abnormally long for a 4-letter word)
        words = [
            Word(word="test", start=4.268, end=8.622, score=0.888),
        ]

        config = CutterConfig()
        corrected = correct_word_timestamps(words, config)

        # Should be corrected to a reasonable duration (< 0.5s for 4 letters)
        assert corrected[0].end - corrected[0].start < 0.5
        assert corrected[0].end - corrected[0].start >= 0.05  # Min 50ms

    def test_test_word_corrected_to_approx_04s(self):
        """The word 'test' (4 chars) should be corrected to ~0.4s max."""
        # Raw WhisperX data: test from 4.268 to 8.622 (4.354s - way too long!)
        words = [
            Word(word="test", start=4.268, end=8.622, score=0.888),
        ]

        config = CutterConfig()
        corrected = correct_word_timestamps(words, config)

        # "test" has 4 chars, max ~0.4s
        duration = corrected[0].end - corrected[0].start
        assert 0.25 < duration < 0.5, f"Expected ~0.4s, got {duration}s"

    def test_normal_word_not_corrected(self):
        """Words with normal duration should not be modified."""
        words = [
            Word(word="bonjour", start=0.0, end=0.5, score=0.9),  # 0.5s is normal
        ]

        config = CutterConfig()
        corrected = correct_word_timestamps(words, config)

        # Should remain unchanged
        assert corrected[0].start == 0.0
        assert corrected[0].end == 0.5

    def test_french_filler_euh_corrected(self):
        """French filler 'euh' should be corrected to ~0.3s if too long."""
        words = [
            Word(word="euh", start=1.0, end=3.5, score=0.7),  # 2.5s is too long
        ]

        config = CutterConfig()
        corrected = correct_word_timestamps(words, config)

        # Should be corrected to known average duration for "euh"
        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.3, abs=0.05)

    def test_filler_hmm_corrected_to_015s(self):
        """The filler 'hmm' should be corrected to ~0.15s if too long."""
        words = [
            Word(word="hmm", start=5.0, end=8.0, score=0.3),  # 3s is too long
        ]

        config = CutterConfig()
        corrected = correct_word_timestamps(words, config)

        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.15, abs=0.05)

    def test_short_word_cas_corrected(self):
        """The word 'cas' (3 letters) should be corrected if too long.

        Regression test for the specific case:
        {"word": "cas", "start": 12.515, "end": 14.479, "score": 0.978}
        Duration: 1.96s (way too long for a 3-letter word)
        Expected max: 0.3s
        """
        words = [
            Word(word="cas", start=12.515, end=14.479, score=0.978),
        ]

        config = CutterConfig()
        corrected = correct_word_timestamps(words, config)

        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.3, abs=0.01), f"'cas' duration {duration}s not ~0.3s"


class TestCorrectionConstraints:
    """Tests for correction constraints and edge cases."""

    def test_corrected_word_does_not_extend_beyond_next_word(self):
        """Corrected word end should not extend beyond next word's start."""
        words = [
            Word(word="test", start=0.0, end=5.0, score=0.8),  # Too long
            Word(word="next", start=0.3, end=0.5, score=0.9),  # Very close!
        ]

        config = CutterConfig()
        corrected = correct_word_timestamps(words, config)

        # First word should not extend past second word's start
        assert corrected[0].end < corrected[1].start

    def test_minimum_duration_50ms(self):
        """Corrected words should have at least 50ms duration."""
        words = [
            Word(word="a", start=0.0, end=10.0, score=0.3),  # Very long
        ]

        config = CutterConfig()
        corrected = correct_word_timestamps(words, config)

        duration = corrected[0].end - corrected[0].start
        assert duration >= 0.05, f"Duration {duration}s is below minimum 50ms"

    def test_empty_words_list(self):
        """Empty word list should return empty list."""
        config = CutterConfig()
        corrected = correct_word_timestamps([], config)
        assert corrected == []

    def test_word_status_preserved(self):
        """Word status should be preserved after correction."""
        words = [
            Word(word="test", start=0.0, end=5.0, score=0.8, status=WordStatus.FILLER),
        ]

        config = CutterConfig()
        corrected = correct_word_timestamps(words, config)

        assert corrected[0].status == WordStatus.FILLER


class TestRealWorldSample:
    """Tests using real-world sample data patterns."""

    def test_sample_test_word_from_whisperx(self):
        """Test the specific 'test' word from sample_whisperx.json.

        Raw data: test from 4.268 to 8.622 (4.354s!)
        Expected: ~0.4s after correction
        """
        words = [
            Word(word="de", start=3.646, end=4.208, score=0.984),
            Word(word="test", start=4.268, end=8.622, score=0.888),
            Word(word="hmm", start=8.642, end=8.702, score=0.241),
        ]

        config = CutterConfig()
        corrected = correct_word_timestamps(words, config)

        # Find the corrected "test" word
        test_word = next(w for w in corrected if w.word == "test")

        # Duration should be reasonable (< 0.5s)
        duration = test_word.end - test_word.start
        assert duration < 0.5, f"'test' duration {duration}s exceeds 0.5s"

        # Should not overlap with next word
        hmm_word = next(w for w in corrected if w.word == "hmm")
        assert test_word.end <= hmm_word.start

    def test_sample_hmm_word_normal_duration(self):
        """Test the 'hmm' word with normal duration (0.06s).

        Words with normal duration should not be corrected.
        """
        words = [
            Word(word="hmm", start=8.642, end=8.702, score=0.241),
        ]

        config = CutterConfig()
        corrected = correct_word_timestamps(words, config)

        # Duration is normal (0.06s), so no correction happens
        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.06, abs=0.01)


class TestAntiRegression:
    """Anti-regression tests to prevent future issues."""

    def test_short_word_never_exceeds_03s_after_correction(self):
        """REGRESSION: 3-letter words must NEVER exceed 0.3s after correction."""
        for raw_end in [5.0, 10.0, 20.0, 50.0]:
            words = [
                Word(word="cas", start=0.0, end=raw_end, score=0.9),
            ]

            config = CutterConfig()
            corrected = correct_word_timestamps(words, config)

            duration = corrected[0].end - corrected[0].start
            assert duration == pytest.approx(0.3, abs=0.01), f"'cas' with raw end={raw_end} not ~0.3s: {duration}s"

    def test_long_words_always_corrected(self):
        """REGRESSION: Any word exceeding its max duration must be corrected."""
        for word_text in ["test", "bonjour", "development", "implementation"]:
            words = [
                Word(word=word_text, start=0.0, end=10.0, score=0.9),
            ]

            config = CutterConfig()
            corrected = correct_word_timestamps(words, config)

            duration = corrected[0].end - corrected[0].start
            # All words should be corrected to <= 1s
            assert duration <= 1.0, f"'{word_text}' was not corrected: {duration}s"
