"""Tests for filler word classification.

These tests verify that:
1. Authorized fillers are correctly detected and cut
2. Forbidden words are NEVER classified as fillers
3. Classification is stable and doesn't regress
"""

import pytest

from derush.models import Word, WordStatus
from derush.cutter import classify_words, is_filler, _build_filler_patterns
from derush.config import DEFAULT_FILLERS


class TestAuthorizedFillers:
    """Tests for words that MUST be classified as fillers."""

    @pytest.mark.parametrize("filler", ["euh", "ben", "bah", "hmm"])
    def test_french_filler_is_detected(self, filler):
        """Authorized French fillers must be detected."""
        words = [
            Word(word=filler, start=0.0, end=0.3, score=0.8),
        ]

        result = classify_words(words, language="fr")

        assert result[0].status == WordStatus.FILLER, f"'{filler}' should be filler"

    @pytest.mark.parametrize("filler", ["um", "uh", "hmm"])
    def test_english_filler_is_detected(self, filler):
        """Authorized English fillers must be detected."""
        words = [
            Word(word=filler, start=0.0, end=0.3, score=0.8),
        ]

        result = classify_words(words, language="en")

        assert result[0].status == WordStatus.FILLER, f"'{filler}' should be filler"

    def test_bon_ben_is_detected(self):
        """The expression 'bon ben' - only 'ben' is detected as filler."""
        words = [
            Word(word="bon", start=0.0, end=0.2, score=0.8),
            Word(word="ben", start=0.2, end=0.4, score=0.8),
        ]

        result = classify_words(words, language="fr")

        # 'bon' alone is kept, 'ben' is a filler
        assert result[0].status == WordStatus.KEPT  # "bon" alone is NOT a filler
        assert result[1].status == WordStatus.FILLER  # "ben" is a filler

    def test_filler_variants_detected(self):
        """Phonetic variants of fillers should be detected."""
        variants = ["mm", "hm", "hmmm", "hmmmm", "euhh", "euhhh", "umm", "uhh"]

        for variant in variants:
            words = [Word(word=variant, start=0.0, end=0.3, score=0.7)]
            result = classify_words(words, language="fr" if variant.startswith("e") else "en")

            assert result[0].status == WordStatus.FILLER, f"Variant '{variant}' should be filler"


class TestForbiddenFillers:
    """Tests for words that must NEVER be classified as fillers."""

    def test_voilà_is_kept(self):
        """'voilà' can be an affirmation, must NOT be cut."""
        words = [
            Word(word="je", start=0.0, end=0.2, score=0.9),
            Word(word="pense", start=0.2, end=0.4, score=0.9),
            Word(word="que", start=0.4, end=0.6, score=0.9),
            Word(word="voilà", start=0.6, end=0.9, score=0.9),
        ]

        result = classify_words(words, language="fr")

        voila_word = next(w for w in result if w.word == "voilà")
        assert voila_word.status == WordStatus.KEPT, "'voilà' must NOT be classified as filler"

    def test_quoi_is_kept(self):
        """'quoi' is part of phrases like 'de quoi', must NOT be cut."""
        words = [
            Word(word="de", start=0.0, end=0.2, score=0.9),
            Word(word="quoi", start=0.2, end=0.4, score=0.9),
            Word(word="par", start=0.4, end=0.6, score=0.9),
            Word(word="le", start=0.6, end=0.8, score=0.9),
            Word(word="ton", start=0.8, end=1.0, score=0.9),
        ]

        result = classify_words(words, language="fr")

        quoi_word = next(w for w in result if w.word == "quoi")
        assert quoi_word.status == WordStatus.KEPT, "'quoi' must NOT be classified as filler"

    def test_du_coup_is_kept(self):
        """'du coup' is a common expression, must NOT be cut."""
        words = [
            Word(word="du", start=0.0, end=0.2, score=0.9),
            Word(word="coup", start=0.2, end=0.4, score=0.9),
        ]

        result = classify_words(words, language="fr")

        assert all(w.status == WordStatus.KEPT for w in result), "'du coup' must NOT be classified as filler"

    def test_en_fait_is_kept(self):
        """'en fait' is a common expression, must NOT be cut."""
        words = [
            Word(word="en", start=0.0, end=0.2, score=0.9),
            Word(word="fait", start=0.2, end=0.4, score=0.9),
        ]

        result = classify_words(words, language="fr")

        assert all(w.status == WordStatus.KEPT for w in result), "'en fait' must NOT be classified as filler"

    def test_bon_alone_is_kept(self):
        """'bon' alone (not 'bon ben') must NOT be cut."""
        words = [
            Word(word="bon", start=0.0, end=0.3, score=0.9),
            Word(word="alors", start=0.3, end=0.6, score=0.9),
        ]

        result = classify_words(words, language="fr")

        bon_word = next(w for w in result if w.word == "bon")
        assert bon_word.status == WordStatus.KEPT, "'bon' alone must NOT be classified as filler"

    @pytest.mark.parametrize("word", ["voilà", "quoi", "bon"])
    def test_forbidden_words_never_fillers(self, word):
        """REGRESSION: These words must NEVER be classified as fillers."""
        patterns = _build_filler_patterns(DEFAULT_FILLERS["fr"])

        assert is_filler(word, patterns) is False, f"'{word}' must not match filler pattern"


class TestSampleRegression:
    """Anti-regression tests using sample.mov data."""

    def test_sample_voilà_is_kept(self):
        """Test that 'voilà' from sample is classified as KEPT."""
        # From sample_whisperx.json
        words = [
            Word(word="voilà", start=12.153, end=12.775, score=0.829),
        ]

        result = classify_words(words, language="fr")

        assert result[0].status == WordStatus.KEPT

    def test_sample_quoi_is_kept(self):
        """Test that 'quoi' from sample is classified as KEPT."""
        # From sample_whisperx.json
        words = [
            Word(word="de", start=14.999, end=15.186, score=0.814),
            Word(word="quoi", start=15.227, end=15.414, score=0.944),
        ]

        result = classify_words(words, language="fr")

        quoi_word = next(w for w in result if w.word == "quoi")
        assert quoi_word.status == WordStatus.KEPT

    def test_sample_hmm_is_filler(self):
        """Test that 'hmm' from sample is classified as FILLER."""
        # From sample_whisperx.json
        words = [
            Word(word="hmm", start=8.642, end=8.702, score=0.241),
        ]

        result = classify_words(words, language="fr")

        assert result[0].status == WordStatus.FILLER

    def test_sample_all_words_classification(self):
        """Test classification of all words from sample."""
        # All words from sample_whisperx.json
        words = [
            Word(word="petite", start=1.6, end=2.543, score=0.806),
            Word(word="démo", start=2.583, end=3.606, score=0.625),
            Word(word="de", start=3.646, end=4.208, score=0.984),
            Word(word="test", start=4.268, end=8.622, score=0.888),
            Word(word="hmm", start=8.642, end=8.702, score=0.241),
            Word(word="je", start=8.742, end=8.883, score=0.967),
            Word(word="pense", start=8.923, end=9.284, score=0.981),
            Word(word="que", start=9.324, end=12.113, score=0.844),
            Word(word="voilà", start=12.153, end=12.775, score=0.829),
            Word(word="de", start=14.999, end=15.186, score=0.814),
            Word(word="quoi", start=15.227, end=15.414, score=0.944),
            Word(word="par", start=15.455, end=15.58, score=0.784),
            Word(word="le", start=15.6, end=15.704, score=0.81),
            Word(word="ton", start=15.725, end=16.741, score=0.884),
        ]

        result = classify_words(words, language="fr")

        # Expected classifications
        expected = {
            "petite": WordStatus.KEPT,
            "démo": WordStatus.KEPT,
            "de": WordStatus.KEPT,
            "test": WordStatus.KEPT,
            "hmm": WordStatus.FILLER,
            "je": WordStatus.KEPT,
            "pense": WordStatus.KEPT,
            "que": WordStatus.KEPT,
            "voilà": WordStatus.KEPT,
            "quoi": WordStatus.KEPT,
            "par": WordStatus.KEPT,
            "le": WordStatus.KEPT,
            "ton": WordStatus.KEPT,
        }

        for word in result:
            expected_status = expected.get(word.word)
            if expected_status:
                assert word.status == expected_status, \
                    f"'{word.word}' expected {expected_status}, got {word.status}"


class TestCustomFillers:
    """Tests for custom filler words."""

    def test_custom_filler_is_detected(self):
        """Custom fillers should be detected."""
        words = [
            Word(word="custom", start=0.0, end=0.3, score=0.9),
        ]

        result = classify_words(words, language="fr", custom_fillers=["custom"])

        assert result[0].status == WordStatus.FILLER

    def test_custom_fillers_merge_with_defaults(self):
        """Custom fillers should be added to default fillers."""
        words = [
            Word(word="euh", start=0.0, end=0.3, score=0.8),
            Word(word="custom", start=0.3, end=0.6, score=0.9),
        ]

        result = classify_words(words, language="fr", custom_fillers=["custom"])

        assert result[0].status == WordStatus.FILLER  # Default filler
        assert result[1].status == WordStatus.FILLER  # Custom filler


class TestCaseInsensitive:
    """Tests for case-insensitive matching."""

    def test_uppercase_filler_detected(self):
        """Uppercase fillers should be detected."""
        words = [
            Word(word="EUH", start=0.0, end=0.3, score=0.8),
        ]

        result = classify_words(words, language="fr")

        assert result[0].status == WordStatus.FILLER

    def test_mixed_case_filler_detected(self):
        """Mixed case fillers should be detected."""
        words = [
            Word(word="Hmm", start=0.0, end=0.3, score=0.8),
        ]

        result = classify_words(words, language="fr")

        assert result[0].status == WordStatus.FILLER


class TestPunctuation:
    """Tests for punctuation handling."""

    def test_filler_with_punctuation_detected(self):
        """Fillers with punctuation should be detected."""
        words = [
            Word(word="euh,", start=0.0, end=0.3, score=0.8),
        ]

        result = classify_words(words, language="fr")

        assert result[0].status == WordStatus.FILLER

    def test_filler_with_trailing_dots_detected(self):
        """Fillers with trailing dots should be detected."""
        words = [
            Word(word="hmm...", start=0.0, end=0.3, score=0.7),
        ]

        result = classify_words(words, language="fr")

        assert result[0].status == WordStatus.FILLER
