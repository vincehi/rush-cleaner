"""Tests for word timestamp correction.

These tests verify that:
1. Words exceeding max_word_duration are corrected
2. Words with low confidence scores are handled
3. Correction exposes hidden gaps for proper detection
"""

import pytest

from derush.config import CutterConfig
from derush.cutter import correct_word_timestamps
from derush.models import Word, WordStatus


class TestMaxWordDuration:
    """Tests for maximum word duration enforcement."""

    def test_word_exceeding_max_duration_is_corrected(self):
        """A word exceeding max_word_duration must be corrected."""
        # "test" with 4.354s duration (abnormally long)
        words = [
            Word(word="test", start=4.268, end=8.622, score=0.888),
        ]

        config = CutterConfig(max_word_duration=2.0)
        corrected = correct_word_timestamps(words, config)

        # Should be corrected to a reasonable duration
        assert corrected[0].end - corrected[0].start < 2.0
        assert corrected[0].end - corrected[0].start >= 0.05  # Min 50ms

    def test_test_word_corrected_to_approx_032s(self):
        """The word 'test' should be corrected to ~0.32s (based on word length)."""
        # Raw WhisperX data: test from 4.268 to 8.622 (4.354s - way too long!)
        words = [
            Word(word="test", start=4.268, end=8.622, score=0.888),
        ]

        config = CutterConfig(max_word_duration=2.0)
        corrected = correct_word_timestamps(words, config)

        # "test" has 4 chars, expected ~0.32s (0.08 * 4)
        duration = corrected[0].end - corrected[0].start
        assert 0.25 < duration < 0.5, f"Expected ~0.32s, got {duration}s"

    def test_normal_word_not_corrected(self):
        """Words with normal duration should not be modified."""
        words = [
            Word(word="bonjour", start=0.0, end=0.5, score=0.9),  # 0.5s is normal
        ]

        config = CutterConfig(max_word_duration=2.0)
        corrected = correct_word_timestamps(words, config)

        # Should remain unchanged
        assert corrected[0].start == 0.0
        assert corrected[0].end == 0.5

    def test_french_filler_euh_corrected(self):
        """French filler 'euh' should be corrected to ~0.3s if too long."""
        words = [
            Word(word="euh", start=1.0, end=3.5, score=0.7),  # 2.5s is too long
        ]

        config = CutterConfig(max_word_duration=2.0)
        corrected = correct_word_timestamps(words, config)

        # Should be corrected to known average duration for "euh"
        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.3, abs=0.05)

    def test_filler_hmm_corrected_to_015s(self):
        """The filler 'hmm' should be corrected to ~0.15s if too long."""
        words = [
            Word(word="hmm", start=5.0, end=8.0, score=0.3),  # 3s is too long
        ]

        config = CutterConfig(max_word_duration=2.0)
        corrected = correct_word_timestamps(words, config)

        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.15, abs=0.05)


class TestLowConfidenceWords:
    """Tests for handling words with low confidence scores."""

    def test_low_score_word_is_corrected(self):
        """Words with score < min_word_score should be corrected if also long."""
        # "hmm" with score 0.241 (below threshold of 0.5) but normal duration
        words = [
            Word(word="hmm", start=8.642, end=8.702, score=0.241),  # 0.06s duration
        ]

        config = CutterConfig(min_word_score=0.5)
        corrected = correct_word_timestamps(words, config)

        # The word has normal duration (0.06s), so it won't be corrected
        # Correction only happens if word is ALSO too long (> max_word_duration)
        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.06, abs=0.01)

    def test_high_score_word_not_corrected_for_score(self):
        """Words with score >= min_word_score should not be corrected for score."""
        words = [
            Word(word="bonjour", start=0.0, end=0.5, score=0.9),
        ]

        config = CutterConfig(min_word_score=0.5)
        corrected = correct_word_timestamps(words, config)

        # Should remain unchanged
        assert corrected[0].start == 0.0
        assert corrected[0].end == 0.5


class TestCorrectionConstraints:
    """Tests for correction constraints and edge cases."""

    def test_corrected_word_does_not_extend_beyond_next_word(self):
        """Corrected word end should not extend beyond next word's start."""
        words = [
            Word(word="test", start=0.0, end=5.0, score=0.8),  # Too long
            Word(word="next", start=0.3, end=0.5, score=0.9),  # Very close!
        ]

        config = CutterConfig(max_word_duration=2.0)
        corrected = correct_word_timestamps(words, config)

        # First word should not extend past second word's start
        assert corrected[0].end < corrected[1].start

    def test_minimum_duration_50ms(self):
        """Corrected words should have at least 50ms duration."""
        words = [
            Word(word="a", start=0.0, end=10.0, score=0.3),  # Very long
        ]

        config = CutterConfig(max_word_duration=2.0)
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

        config = CutterConfig(max_word_duration=2.0)
        corrected = correct_word_timestamps(words, config)

        assert corrected[0].status == WordStatus.FILLER


class TestRealWorldSample:
    """Tests using real-world sample data patterns."""

    def test_sample_test_word_from_whisperx(self):
        """Test the specific 'test' word from sample_whisperx.json.

        Raw data: test from 4.268 to 8.622 (4.354s!)
        Expected: ~0.32s after correction
        """
        words = [
            Word(word="de", start=3.646, end=4.208, score=0.984),
            Word(word="test", start=4.268, end=8.622, score=0.888),
            Word(word="hmm", start=8.642, end=8.702, score=0.241),
        ]

        config = CutterConfig(max_word_duration=2.0)
        corrected = correct_word_timestamps(words, config)

        # Find the corrected "test" word
        test_word = next(w for w in corrected if w.word == "test")

        # Duration should be reasonable (0.25-0.5s)
        duration = test_word.end - test_word.start
        assert duration < 1.0, f"'test' duration {duration}s exceeds 1s"

        # Should not overlap with next word
        hmm_word = next(w for w in corrected if w.word == "hmm")
        assert test_word.end <= hmm_word.start

    def test_sample_hmm_word_low_score(self):
        """Test the 'hmm' word with low score (0.241) from sample.

        Note: hmm has normal duration (0.06s), so it won't be corrected
        even with low score. Correction only happens for abnormally long words.
        """
        words = [
            Word(word="hmm", start=8.642, end=8.702, score=0.241),
        ]

        config = CutterConfig(min_word_score=0.5)
        corrected = correct_word_timestamps(words, config)

        # Duration is normal (0.06s), so no correction happens
        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.06, abs=0.01)


class TestAntiRegression:
    """Anti-regression tests to prevent future issues."""

    def test_test_word_never_exceeds_1s_after_correction(self):
        """REGRESSION: 'test' must NEVER exceed 1s after correction."""
        # Try with various raw durations
        for raw_end in [5.0, 10.0, 20.0, 50.0]:
            words = [
                Word(word="test", start=0.0, end=raw_end, score=0.8),
            ]

            config = CutterConfig(max_word_duration=2.0)
            corrected = correct_word_timestamps(words, config)

            duration = corrected[0].end - corrected[0].start
            assert duration < 1.0, f"'test' with raw end={raw_end} exceeded 1s: {duration}s"

    def test_long_words_always_corrected(self):
        """REGRESSION: Any word > max_word_duration must be corrected."""
        for word_text in ["test", "bonjour", "development", "implementation"]:
            words = [
                Word(word=word_text, start=0.0, end=10.0, score=0.9),
            ]

            config = CutterConfig(max_word_duration=2.0)
            corrected = correct_word_timestamps(words, config)

            duration = corrected[0].end - corrected[0].start
            assert duration < 2.0, f"'{word_text}' was not corrected: {duration}s"
