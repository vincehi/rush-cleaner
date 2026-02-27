"""Tests for filler_detector module."""

import pytest

from src.models import Segment, Word
from src.filler_detector import detect_fillers, _normalize_word


class TestNormalizeWord:
    """Tests for _normalize_word function."""

    def test_lowercase(self):
        """Test conversion to lowercase."""
        assert _normalize_word("UM") == "um"
        assert _normalize_word("EUH") == "euh"

    def test_strip_punctuation(self):
        """Test removal of punctuation."""
        assert _normalize_word("um,") == "um"
        assert _normalize_word("euh.") == "euh"
        assert _normalize_word("!like") == "like"


class TestDetectFillers:
    """Tests for detect_fillers function."""

    def test_detect_french_fillers(self):
        """Test detection of French filler words."""
        words = [
            Word(word="Bonjour", start=0.0, end=0.5, score=0.9),
            Word(word="euh", start=0.6, end=0.8, score=0.8),
            Word(word="comment", start=0.9, end=1.2, score=0.9),
            Word(word="ça", start=1.3, end=1.5, score=0.9),
            Word(word="va", start=1.6, end=1.8, score=0.9),
        ]

        segments = [
            Segment(start=0.0, end=1.8, text="Bonjour euh comment ça va", words=words)
        ]

        result = detect_fillers(segments, language="fr")

        assert len(result) == 1
        assert result[0].cut_type == "filler"
        assert "euh" in result[0].label.lower()

    def test_detect_english_fillers(self):
        """Test detection of English filler words."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9),
            Word(word="um", start=0.6, end=0.8, score=0.8),
            Word(word="how", start=0.9, end=1.2, score=0.9),
            Word(word="are", start=1.3, end=1.5, score=0.9),
            Word(word="you", start=1.6, end=1.8, score=0.9),
        ]

        segments = [
            Segment(start=0.0, end=1.8, text="Hello um how are you", words=words)
        ]

        result = detect_fillers(segments, language="en")

        assert len(result) == 1
        assert result[0].cut_type == "filler"
        assert "um" in result[0].label.lower()

    def test_no_fillers(self):
        """Test with no filler words present."""
        words = [
            Word(word="Bonjour", start=0.0, end=0.5, score=0.9),
            Word(word="tout", start=0.6, end=0.8, score=0.9),
            Word(word="le", start=0.9, end=1.0, score=0.9),
            Word(word="monde", start=1.1, end=1.4, score=0.9),
        ]

        segments = [
            Segment(start=0.0, end=1.4, text="Bonjour tout le monde", words=words)
        ]

        result = detect_fillers(segments, language="fr")

        assert len(result) == 0

    def test_ignore_false_positives(self):
        """Test that filler-like words inside other words are ignored."""
        words = [
            Word(word="umbrella", start=0.0, end=0.8, score=0.9),
            Word(word="humid", start=1.0, end=1.5, score=0.9),
        ]

        segments = [
            Segment(start=0.0, end=1.5, text="umbrella humid", words=words)
        ]

        result = detect_fillers(segments, language="en")

        # "um" in "umbrella" and "hmm" in "humid" should not be detected
        # because we match whole words only
        assert len(result) == 0

    def test_custom_fillers(self):
        """Test detection with custom filler words."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9),
            Word(word="custom", start=0.6, end=0.9, score=0.9),
            Word(word="there", start=1.0, end=1.3, score=0.9),
        ]

        segments = [
            Segment(start=0.0, end=1.3, text="Hello custom there", words=words)
        ]

        result = detect_fillers(segments, language="en", custom_fillers=["custom"])

        assert len(result) == 1
        assert "custom" in result[0].label.lower()

    def test_phonetic_variants(self):
        """Test detection of phonetic variants (mm, hm, hmm for um)."""
        words = [
            Word(word="well", start=0.0, end=0.3, score=0.9),
            Word(word="mm", start=0.4, end=0.6, score=0.7),
            Word(word="okay", start=0.7, end=1.0, score=0.9),
        ]

        segments = [
            Segment(start=0.0, end=1.0, text="well mm okay", words=words)
        ]

        result = detect_fillers(segments, language="en")

        assert len(result) == 1
        assert result[0].cut_type == "filler"

    def test_multi_word_fillers(self):
        """Test detection of multi-word fillers."""
        words = [
            Word(word="it's", start=0.0, end=0.3, score=0.9),
            Word(word="like", start=0.4, end=0.6, score=0.9),
            Word(word="really", start=0.7, end=1.0, score=0.9),
            Word(word="cool", start=1.1, end=1.4, score=0.9),
        ]

        segments = [
            Segment(start=0.0, end=1.4, text="it's like really cool", words=words)
        ]

        result = detect_fillers(segments, language="en")

        # "like" should be detected as a filler
        assert len(result) >= 1
        assert any("like" in c.label.lower() for c in result)

    def test_multiple_fillers_in_segment(self):
        """Test detection of multiple fillers in a single segment."""
        words = [
            Word(word="ben", start=0.0, end=0.3, score=0.8),
            Word(word="je", start=0.4, end=0.6, score=0.9),
            Word(word="euh", start=0.7, end=0.9, score=0.8),
            Word(word="sais", start=1.0, end=1.2, score=0.9),
            Word(word="pas", start=1.3, end=1.5, score=0.9),
        ]

        segments = [
            Segment(start=0.0, end=1.5, text="ben je euh sais pas", words=words)
        ]

        result = detect_fillers(segments, language="fr")

        # Should detect "ben" and "euh"
        assert len(result) == 2
        filler_words = [c.label.lower() for c in result]
        assert any("ben" in w for w in filler_words)
        assert any("euh" in w for w in filler_words)
