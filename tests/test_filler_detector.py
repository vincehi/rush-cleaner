"""Tests for filler_detector module."""

import pytest

from src.models import Segment, Word
from src.filler_detector import (
    detect_fillers,
    _normalize_word,
    get_keep_segments,
    is_filler,
    _build_filler_patterns,
    _merge_ranges,
    TimeRange,
)


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

    def test_segment_level_fallback_filler_only_segment(self):
        """Segment with no word-level alignment but text 'hmm...' is detected as filler."""
        # Simulates WhisperX returning a segment for "hmm..." without word-level words
        segments = [
            Segment(start=0.0, end=1.2, text="Petite démo de test.", words=[
                Word(word="Petite", start=0.0, end=0.3, score=0.9),
                Word(word="démo", start=0.35, end=0.6, score=0.9),
                Word(word="de", start=0.65, end=0.8, score=0.9),
                Word(word="test", start=0.85, end=1.2, score=0.9),
            ]),
            Segment(start=1.2, end=1.8, text="hmm...", words=[]),
            Segment(start=1.8, end=2.5, text="Je pense que...", words=[
                Word(word="Je", start=1.8, end=1.9, score=0.9),
                Word(word="pense", start=1.95, end=2.2, score=0.9),
                Word(word="que", start=2.25, end=2.5, score=0.9),
            ]),
        ]

        result = detect_fillers(segments, language="fr")

        assert len(result) == 1
        assert result[0].cut_type == "filler"
        assert result[0].start == 1.2
        assert result[0].end == 1.8
        assert "hmm" in result[0].label.lower()


class TestIsFiller:
    """Tests for is_filler function."""

    def test_basic_filler_detection(self):
        """Test detection of basic filler words."""
        patterns = _build_filler_patterns(["euh", "um"])
        assert is_filler("euh", patterns) is True
        assert is_filler("um", patterns) is True
        assert is_filler("hello", patterns) is False

    def test_filler_variants(self):
        """Test detection of filler variants."""
        patterns = _build_filler_patterns(["um", "hmm"])
        assert is_filler("mm", patterns) is True
        assert is_filler("hmm", patterns) is True
        assert is_filler("hmmm", patterns) is True
        assert is_filler("umm", patterns) is True

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        patterns = _build_filler_patterns(["euh"])
        assert is_filler("EUH", patterns) is True
        assert is_filler("Euh", patterns) is True

    def test_punctuation_ignored(self):
        """Test that punctuation is stripped before matching."""
        patterns = _build_filler_patterns(["euh"])
        assert is_filler("euh...", patterns) is True
        assert is_filler("euh,", patterns) is True


class TestMergeRanges:
    """Tests for _merge_ranges function."""

    def test_empty_ranges(self):
        """Test with empty input."""
        assert _merge_ranges([]) == []

    def test_single_range(self):
        """Test with single range."""
        ranges = [TimeRange(start=0.0, end=1.0)]
        result = _merge_ranges(ranges)
        assert len(result) == 1
        assert result[0].start == 0.0
        assert result[0].end == 1.0

    def test_adjacent_ranges_merged(self):
        """Test that adjacent ranges are merged."""
        ranges = [
            TimeRange(start=0.0, end=1.0),
            TimeRange(start=1.0, end=2.0),
        ]
        result = _merge_ranges(ranges)
        assert len(result) == 1
        assert result[0].start == 0.0
        assert result[0].end == 2.0

    def test_overlapping_ranges_merged(self):
        """Test that overlapping ranges are merged."""
        ranges = [
            TimeRange(start=0.0, end=1.5),
            TimeRange(start=1.0, end=2.0),
        ]
        result = _merge_ranges(ranges)
        assert len(result) == 1
        assert result[0].start == 0.0
        assert result[0].end == 2.0

    def test_separate_ranges_not_merged(self):
        """Test that separate ranges are not merged."""
        ranges = [
            TimeRange(start=0.0, end=1.0),
            TimeRange(start=2.0, end=3.0),
        ]
        result = _merge_ranges(ranges)
        assert len(result) == 2

    def test_tolerance_gap(self):
        """Test that gaps within tolerance are merged."""
        ranges = [
            TimeRange(start=0.0, end=1.0),
            TimeRange(start=1.03, end=2.0),  # 0.03s gap, within 0.05s tolerance
        ]
        result = _merge_ranges(ranges, tolerance=0.05)
        assert len(result) == 1

    def test_gap_exceeds_tolerance(self):
        """Test that gaps exceeding tolerance are not merged."""
        ranges = [
            TimeRange(start=0.0, end=1.0),
            TimeRange(start=1.1, end=2.0),  # 0.1s gap, exceeds 0.05s tolerance
        ]
        result = _merge_ranges(ranges, tolerance=0.05)
        assert len(result) == 2

    def test_unsorted_ranges(self):
        """Test that unsorted ranges are handled correctly."""
        ranges = [
            TimeRange(start=2.0, end=3.0),
            TimeRange(start=0.0, end=1.0),
            TimeRange(start=1.0, end=2.0),
        ]
        result = _merge_ranges(ranges)
        assert len(result) == 1
        assert result[0].start == 0.0
        assert result[0].end == 3.0


class TestGetKeepSegments:
    """Tests for get_keep_segments function (new "words to keep" approach)."""

    def test_basic_keep_segments(self):
        """Test basic content detection with filler removal."""
        words = [
            Word(word="Bonjour", start=0.0, end=0.5, score=0.9),
            Word(word="euh", start=0.5, end=0.7, score=0.8),
            Word(word="comment", start=0.7, end=1.0, score=0.9),
        ]
        segments = [Segment(start=0.0, end=1.0, text="Bonjour euh comment", words=words)]

        cuts = get_keep_segments(segments, language="fr", total_duration=1.0)

        # Should have one cut for the filler "euh"
        assert len(cuts) == 1
        assert cuts[0].start == 0.5
        assert cuts[0].end == 0.7

    def test_keep_all_content_no_fillers(self):
        """Test that content without fillers produces no cuts."""
        words = [
            Word(word="Bonjour", start=0.0, end=0.5, score=0.9),
            Word(word="comment", start=0.5, end=0.8, score=0.9),
            Word(word="ça", start=0.8, end=1.0, score=0.9),
        ]
        segments = [Segment(start=0.0, end=1.0, text="Bonjour comment ça", words=words)]

        cuts = get_keep_segments(segments, language="fr", total_duration=1.0)

        assert len(cuts) == 0

    def test_silence_at_beginning(self):
        """Test silence detection at the beginning."""
        words = [
            Word(word="Hello", start=1.0, end=1.5, score=0.9),
        ]
        segments = [Segment(start=1.0, end=1.5, text="Hello", words=words)]

        cuts = get_keep_segments(segments, language="en", min_silence=0.5, total_duration=2.0)

        # Should have a cut for the silence at the beginning (0.0 to 1.0)
        assert len(cuts) >= 1
        silence_cut = next((c for c in cuts if c.start == 0.0), None)
        assert silence_cut is not None
        assert silence_cut.end == 1.0
        assert silence_cut.cut_type == "silence"

    def test_silence_at_end(self):
        """Test silence detection at the end."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9),
        ]
        segments = [Segment(start=0.0, end=0.5, text="Hello", words=words)]

        cuts = get_keep_segments(segments, language="en", min_silence=0.5, total_duration=2.0)

        # Should have a cut for the silence at the end (0.5 to 2.0)
        assert len(cuts) >= 1
        end_cut = next((c for c in cuts if c.end == 2.0), None)
        assert end_cut is not None
        assert end_cut.start == 0.5

    def test_silence_between_segments(self):
        """Test silence detection between segments."""
        segments = [
            Segment(start=0.0, end=0.5, text="First", words=[
                Word(word="First", start=0.0, end=0.5, score=0.9)
            ]),
            Segment(start=2.0, end=2.5, text="Second", words=[
                Word(word="Second", start=2.0, end=2.5, score=0.9)
            ]),
        ]

        cuts = get_keep_segments(segments, language="en", min_silence=0.5, total_duration=3.0)

        # Should have a cut for the silence between segments (0.5 to 2.0)
        gap_cut = next((c for c in cuts if c.start == 0.5 and c.end == 2.0), None)
        assert gap_cut is not None

    def test_min_silence_filter(self):
        """Test that short silences are not cut."""
        segments = [
            Segment(start=0.0, end=1.0, text="First", words=[
                Word(word="First", start=0.0, end=1.0, score=0.9)
            ]),
            Segment(start=1.2, end=2.0, text="Second", words=[
                Word(word="Second", start=1.2, end=2.0, score=0.9)
            ]),
        ]

        # Gap is 0.2s, with min_silence=0.5 it should NOT be cut
        cuts = get_keep_segments(segments, language="en", min_silence=0.5, total_duration=2.0)

        # No gap cut should exist
        gap_cut = next((c for c in cuts if c.start == 1.0 and c.end == 1.2), None)
        assert gap_cut is None

    def test_segment_without_words_kept_if_not_filler(self):
        """Test that segments without word alignment are kept if not filler."""
        segments = [
            Segment(start=0.0, end=1.0, text="Some text", words=[]),
        ]

        cuts = get_keep_segments(segments, language="en", min_silence=0.5, total_duration=1.0)

        # Segment should be kept (no cuts)
        assert len(cuts) == 0

    def test_segment_without_words_cut_if_filler(self):
        """Test that segments without word alignment are cut if filler."""
        segments = [
            Segment(start=0.0, end=1.0, text="hmm...", words=[]),
        ]

        cuts = get_keep_segments(segments, language="en", min_silence=0.5, total_duration=1.0)

        # Filler segment should be cut
        assert len(cuts) == 1
        assert cuts[0].start == 0.0
        assert cuts[0].end == 1.0

    def test_custom_fillers(self):
        """Test custom filler words."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9),
            Word(word="custom", start=0.5, end=0.8, score=0.9),
            Word(word="there", start=0.8, end=1.0, score=0.9),
        ]
        segments = [Segment(start=0.0, end=1.0, text="Hello custom there", words=words)]

        cuts = get_keep_segments(
            segments,
            language="en",
            custom_fillers=["custom"],
            total_duration=1.0
        )

        # "custom" should be cut
        assert len(cuts) == 1
        assert cuts[0].start == 0.5
        assert cuts[0].end == 0.8

    def test_multiple_fillers_and_silences(self):
        """Test combined fillers and silences."""
        segments = [
            Segment(start=0.0, end=1.0, text="Hello euh world", words=[
                Word(word="Hello", start=0.0, end=0.4, score=0.9),
                Word(word="euh", start=0.4, end=0.6, score=0.8),
                Word(word="world", start=0.6, end=1.0, score=0.9),
            ]),
            # 1.0s gap (silence)
            Segment(start=2.0, end=3.0, text="Test um done", words=[
                Word(word="Test", start=2.0, end=2.4, score=0.9),
                Word(word="um", start=2.4, end=2.6, score=0.8),
                Word(word="done", start=2.6, end=3.0, score=0.9),
            ]),
        ]

        cuts = get_keep_segments(segments, language="fr", min_silence=0.5, total_duration=4.0)

        # Should have cuts for: silence at end, silence gap, and fillers within segments
        assert len(cuts) >= 2

    def test_no_segments_entire_silence(self):
        """Test that empty segments result in entire file being cut."""
        cuts = get_keep_segments([], language="en", min_silence=0.5, total_duration=5.0)

        assert len(cuts) == 1
        assert cuts[0].start == 0.0
        assert cuts[0].end == 5.0

    def test_phonetic_variants_detected(self):
        """Test that phonetic variants are detected as fillers."""
        words = [
            Word(word="well", start=0.0, end=0.3, score=0.9),
            Word(word="mm", start=0.3, end=0.5, score=0.7),
            Word(word="okay", start=0.5, end=0.8, score=0.9),
        ]
        segments = [Segment(start=0.0, end=0.8, text="well mm okay", words=words)]

        cuts = get_keep_segments(segments, language="en", total_duration=0.8)

        # "mm" should be cut
        assert len(cuts) == 1
        assert cuts[0].start == 0.3
        assert cuts[0].end == 0.5
