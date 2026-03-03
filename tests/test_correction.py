"""Tests for word timestamp correction with V2 pipeline.

These tests verify that:
1. Words exceeding their expected duration (based on length) are corrected
2. Correction exposes hidden gaps for proper detection
"""

import pytest

from derush.cutter import correct_word_timestamps, estimate_word_duration
from derush.models import Word, WordStatus


class TestDurationBasedCorrection:
    """Tests for duration-based word correction (based on word length)."""

    def test_word_exceeding_expected_duration_is_corrected(self):
        """A word exceeding its expected duration must be corrected."""
        # "test" with 4.354s duration (abnormally long for a 4-letter word)
        words = [
            Word(word="test", start=4.268, end=8.622, score=0.888),
        ]

        corrected, count = correct_word_timestamps(words)

        # Should be corrected to a reasonable duration (< 0.5s for 4 letters)
        assert corrected[0].end - corrected[0].start < 0.5
        assert corrected[0].end - corrected[0].start >= 0.05  # Min 50ms
        assert count == 1

    def test_test_word_corrected_to_approx_04s(self):
        """The word 'test' (4 chars) should be corrected to ~0.35s max."""
        # Raw WhisperX data: test from 4.268 to 8.622 (4.354s - way too long!)
        words = [
            Word(word="test", start=4.268, end=8.622, score=0.888),
        ]

        corrected, count = correct_word_timestamps(words)

        # "test" has 4 chars, max ~0.35s (TIMING_5LETTER_MAX)
        duration = corrected[0].end - corrected[0].start
        assert 0.25 < duration < 0.5, f"Expected ~0.35s, got {duration}s"
        assert count == 1

    def test_normal_word_not_corrected(self):
        """Words with normal duration should not be modified."""
        # "bonjour" (7 letters) with 0.5s duration is normal
        words = [
            Word(word="bonjour", start=0.0, end=0.5, score=0.9),
        ]

        corrected, count = correct_word_timestamps(words)

        # Should remain unchanged (0.5s < 0.55s max for 7 letters)
        assert corrected[0].start == 0.0
        assert corrected[0].end == 0.5
        assert count == 0

    def test_french_filler_euh_corrected(self):
        """French filler 'euh' should be corrected to ~0.2s if too long."""
        words = [
            Word(word="euh", start=1.0, end=3.5, score=0.7),  # 2.5s is too long
        ]

        corrected, count = correct_word_timestamps(words)

        # Should be corrected to TIMING_3LETTER_MAX (0.20s)
        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.20, abs=0.05)
        assert count == 1

    def test_filler_hmm_corrected_to_02s(self):
        """The filler 'hmm' should be corrected to ~0.2s if too long."""
        words = [
            Word(word="hmm", start=5.0, end=8.0, score=0.3),  # 3s is too long
        ]

        corrected, count = correct_word_timestamps(words)

        # "hmm" has 3 letters, max TIMING_3LETTER_MAX (0.20s)
        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.20, abs=0.05)
        assert count == 1

    def test_short_word_cas_corrected(self):
        """The word 'cas' (3 letters) should be corrected if too long.

        Regression test for the specific case:
        {"word": "cas", "start": 12.515, "end": 14.479, "score": 0.978}
        Duration: 1.96s (way too long for a 3-letter word)
        Expected max: 0.2s (TIMING_3LETTER_MAX)
        """
        words = [
            Word(word="cas", start=12.515, end=14.479, score=0.978),
        ]

        corrected, count = correct_word_timestamps(words)

        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.20, abs=0.01), f"'cas' duration {duration}s not ~0.2s"
        assert count == 1


class TestCorrectionConstraints:
    """Tests for correction constraints and edge cases."""

    def test_corrected_word_does_not_extend_beyond_next_word(self):
        """Corrected word end should not extend beyond next word's start."""
        words = [
            Word(word="test", start=0.0, end=5.0, score=0.8),  # Too long
            Word(word="next", start=0.3, end=0.5, score=0.9),  # Very close!
        ]

        corrected, count = correct_word_timestamps(words)

        # First word should not extend past second word's start
        assert corrected[0].end < corrected[1].start
        assert count == 1

    def test_minimum_duration_50ms(self):
        """Corrected words should have at least 50ms duration."""
        words = [
            Word(word="a", start=0.0, end=10.0, score=0.3),  # Very long
        ]

        corrected, count = correct_word_timestamps(words)

        duration = corrected[0].end - corrected[0].start
        assert duration >= 0.05, f"Duration {duration}s is below minimum 50ms"
        assert count == 1

    def test_empty_words_list(self):
        """Empty word list should return empty list."""
        corrected, count = correct_word_timestamps([])
        assert corrected == []
        assert count == 0

    def test_word_status_preserved(self):
        """Word status should be preserved after correction."""
        words = [
            Word(word="test", start=0.0, end=5.0, score=0.8, status=WordStatus.FILLER),
        ]

        corrected, count = correct_word_timestamps(words)

        assert corrected[0].status == WordStatus.FILLER
        assert count == 1


class TestRealWorldSample:
    """Tests using real-world sample data patterns."""

    def test_sample_test_word_from_whisperx(self):
        """Test the specific 'test' word from sample_whisperx.json.

        Raw data: test from 4.268 to 8.622 (4.354s!)
        Expected: ~0.35s after correction
        """
        words = [
            Word(word="de", start=3.646, end=4.208, score=0.984),
            Word(word="test", start=4.268, end=8.622, score=0.888),
            Word(word="hmm", start=8.642, end=8.702, score=0.241),
        ]

        corrected, count = correct_word_timestamps(words)

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

        corrected, count = correct_word_timestamps(words)

        # Duration is normal (0.06s), so no correction happens
        duration = corrected[0].end - corrected[0].start
        assert duration == pytest.approx(0.06, abs=0.01)
        assert count == 0


class TestAntiRegression:
    """Anti-regression tests to prevent future issues."""

    def test_short_word_never_exceeds_02s_after_correction(self):
        """REGRESSION: 3-letter words must NEVER exceed 0.2s after correction."""
        for raw_end in [5.0, 10.0, 20.0, 50.0]:
            words = [
                Word(word="cas", start=0.0, end=raw_end, score=0.9),
            ]

            corrected, count = correct_word_timestamps(words)

            duration = corrected[0].end - corrected[0].start
            assert duration == pytest.approx(0.20, abs=0.01), (
                f"'cas' with raw end={raw_end} not ~0.2s: {duration}s"
            )
            assert count == 1

    def test_long_words_always_corrected(self):
        """REGRESSION: Any word exceeding its max duration must be corrected."""
        for word_text in ["test", "bonjour", "development", "implementation"]:
            words = [
                Word(word=word_text, start=0.0, end=10.0, score=0.9),
            ]

            corrected, count = correct_word_timestamps(words)

            duration = corrected[0].end - corrected[0].start
            # All words should be corrected to <= 1.5s (max cap)
            assert duration <= 1.5, f"'{word_text}' was not corrected: {duration}s"
            assert count == 1


class TestEstimateWordDuration:
    """Tests for the estimate_word_duration function."""

    def test_short_words_1_2_letters(self):
        """1-2 letter words get minimum duration."""
        assert estimate_word_duration("le") == 0.15
        assert estimate_word_duration("de") == 0.15
        assert estimate_word_duration("a") == 0.15

    def test_3_letter_words(self):
        """3-letter words get 0.20s max."""
        assert estimate_word_duration("cas") == 0.20
        assert estimate_word_duration("pas") == 0.20

    def test_4_5_letter_words(self):
        """4-5 letter words get 0.35s max."""
        assert estimate_word_duration("test") == 0.35
        # "voiture" has 7 letters, so it's in 6-8 category
        assert estimate_word_duration("voiture") == 0.55

    def test_6_8_letter_words(self):
        """6-8 letter words get 0.55s max."""
        # "maintenant" has 10 letters, so it's in 9+ category
        assert estimate_word_duration("maintenant") == 0.8
        # "manger" has 6 letters
        assert estimate_word_duration("manger") == 0.55
        # "ordinateur" has 10 letters
        assert estimate_word_duration("ordinateur") == 0.8

    def test_9_12_letter_words(self):
        """9+ letter words get 0.08s per char, capped at 1.5s."""
        # "developpement" = 13 chars -> 13 * 0.08 = 1.04s
        assert estimate_word_duration("developpement") == 1.04
        # "anticonstitutionnellement" = 24 chars -> 24 * 0.08 = 1.92s, capped at 1.5s
        assert estimate_word_duration("anticonstitutionnellement") == 1.5

