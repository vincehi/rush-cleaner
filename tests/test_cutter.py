"""Tests for cutter module."""

import pytest

from derush.config import CutterConfig
from derush.cutter import (
    _build_filler_patterns,
    _normalize_word,
    classify_words,
    compute_cuts,
    compute_keep_segments,
    is_filler,
)
from derush.models import CutReason, CutType, Word, WordStatus


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

    def test_ignore_false_positives(self):
        """Test that filler-like words inside other words are ignored."""
        patterns = _build_filler_patterns(["um", "hmm"])
        # "um" in "umbrella" should not be detected
        assert is_filler("umbrella", patterns) is False
        # "hmm" in "humid" should not be detected
        assert is_filler("humid", patterns) is False


class TestClassifyWords:
    """Tests for classify_words function."""

    def test_detect_french_fillers(self):
        """Test detection of French filler words."""
        words = [
            Word(word="Bonjour", start=0.0, end=0.5, score=0.9),
            Word(word="euh", start=0.6, end=0.8, score=0.8),
            Word(word="comment", start=0.9, end=1.2, score=0.9),
        ]

        result = classify_words(words, language="fr")

        assert result[0].status == WordStatus.KEPT
        assert result[1].status == WordStatus.FILLER
        assert result[2].status == WordStatus.KEPT

    def test_detect_english_fillers(self):
        """Test detection of English filler words."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9),
            Word(word="um", start=0.6, end=0.8, score=0.8),
            Word(word="how", start=0.9, end=1.2, score=0.9),
        ]

        result = classify_words(words, language="en")

        assert result[0].status == WordStatus.KEPT
        assert result[1].status == WordStatus.FILLER
        assert result[2].status == WordStatus.KEPT

    def test_no_fillers(self):
        """Test with no filler words present."""
        words = [
            Word(word="Bonjour", start=0.0, end=0.5, score=0.9),
            Word(word="tout", start=0.6, end=0.8, score=0.9),
            Word(word="le", start=0.9, end=1.0, score=0.9),
            Word(word="monde", start=1.1, end=1.4, score=0.9),
        ]

        result = classify_words(words, language="fr")

        assert all(w.status == WordStatus.KEPT for w in result)

    def test_custom_fillers(self):
        """Test detection with custom filler words."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9),
            Word(word="custom", start=0.6, end=0.9, score=0.9),
            Word(word="there", start=1.0, end=1.3, score=0.9),
        ]

        result = classify_words(words, language="en", custom_fillers=["custom"])

        assert result[1].status == WordStatus.FILLER

    def test_phonetic_variants(self):
        """Test detection of phonetic variants (mm, hm, hmm for um)."""
        words = [
            Word(word="well", start=0.0, end=0.3, score=0.9),
            Word(word="mm", start=0.4, end=0.6, score=0.7),
            Word(word="okay", start=0.7, end=1.0, score=0.9),
        ]

        result = classify_words(words, language="en")

        assert result[1].status == WordStatus.FILLER


class TestComputeCuts:
    """Tests for compute_cuts function."""

    def test_filler_cut(self):
        """Test that fillers are cut."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="um", start=0.5, end=0.7, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=0.7, end=1.0, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=1.0)

        # Should have a cut for the filler
        filler_cut = next((c for c in cuts if c.cut_type == CutType.FILLER), None)
        assert filler_cut is not None
        assert filler_cut.start == 0.5
        assert filler_cut.end == 0.7
        assert filler_cut.word == "um"

    def test_silence_at_beginning(self):
        """Test silence detection at the beginning."""
        words = [
            Word(word="Hello", start=1.0, end=1.5, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig(min_silence=0.5)
        cuts = compute_cuts(words, config, total_duration=2.0)

        # Should have a cut for the silence at the beginning (0.0 to 1.0)
        silence_cut = next((c for c in cuts if c.reason == CutReason.GAP_BEFORE_SPEECH), None)
        assert silence_cut is not None
        assert silence_cut.start == 0.0
        assert silence_cut.end == 1.0

    def test_silence_at_end(self):
        """Test silence detection at the end."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig(min_silence=0.5)
        cuts = compute_cuts(words, config, total_duration=2.0)

        # Should have a cut for the silence at the end (0.5 to 2.0)
        end_cut = next((c for c in cuts if c.reason == CutReason.GAP_AFTER_SPEECH), None)
        assert end_cut is not None
        assert end_cut.start == 0.5
        assert end_cut.end == 2.0

    def test_silence_between_segments(self):
        """Test silence detection between segments (large gaps)."""
        words = [
            Word(word="First", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="Second", start=2.0, end=2.5, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig(min_silence=0.5)
        cuts = compute_cuts(words, config, total_duration=3.0)

        # Should have a cut for the gap between words (0.5 to 2.0)
        gap_cut = next((c for c in cuts if c.reason == CutReason.GAP_BETWEEN_SEGMENTS), None)
        assert gap_cut is not None
        assert gap_cut.start == 0.5
        assert gap_cut.end == 2.0

    def test_min_silence_filter(self):
        """Test that short silences are not cut."""
        words = [
            Word(word="First", start=0.0, end=1.0, score=0.9, status=WordStatus.KEPT),
            Word(word="Second", start=1.2, end=2.0, score=0.9, status=WordStatus.KEPT),
        ]

        # Gap is 0.2s, below default min_gap_cut (0.3) → not cut
        config = CutterConfig(min_silence=0.5)
        cuts = compute_cuts(words, config, total_duration=2.0)

        # No gap cut should exist
        gap_cut = next((c for c in cuts if c.start == 1.0 and c.end == 1.2), None)
        assert gap_cut is None

    def test_min_gap_cut_controls_gap_between_segments(self):
        """Gap-between-segments threshold is min_gap_cut, not min_silence."""
        words = [
            Word(word="A", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="B", start=0.9, end=1.2, score=0.9, status=WordStatus.KEPT),
        ]
        # Gap = 0.4s
        config_low = CutterConfig(min_silence=0.5, min_gap_cut=0.3)
        cuts_low = compute_cuts(words, config_low, total_duration=2.0)
        gap_cut_low = next(
            (c for c in cuts_low if c.reason == CutReason.GAP_BETWEEN_SEGMENTS), None
        )
        assert gap_cut_low is not None
        assert gap_cut_low.start == 0.5
        assert gap_cut_low.end == 0.9

        config_high = CutterConfig(min_silence=0.5, min_gap_cut=0.5)
        cuts_high = compute_cuts(words, config_high, total_duration=2.0)
        gap_cut_high = next(
            (c for c in cuts_high if c.reason == CutReason.GAP_BETWEEN_SEGMENTS), None
        )
        assert gap_cut_high is None  # 0.4s < 0.5

    def test_gap_after_filler_cut(self):
        """Test that gaps after fillers are cut when enabled."""
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="um", start=0.5, end=0.6, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=0.9, end=1.2, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig(gap_after_filler=True)
        cuts = compute_cuts(words, config, total_duration=1.5)

        # Should have a merged cut (filler + gap after)
        # The filler is at 0.5-0.6, gap is 0.6-0.9, so merged cut is 0.5-0.9
        merged_cut = next((c for c in cuts if c.start == 0.5), None)
        assert merged_cut is not None
        assert merged_cut.end >= 0.6  # Should include the gap

    def test_no_words_entire_silence(self):
        """Test that no words results in entire file being cut."""
        config = CutterConfig()
        cuts = compute_cuts([], config, total_duration=5.0)

        assert len(cuts) == 1
        assert cuts[0].start == 0.0
        assert cuts[0].end == 5.0


class TestComputeKeepSegments:
    """Tests for compute_keep_segments function."""

    def test_basic_keep_segments(self):
        """Test basic keep segment computation."""
        from derush.models import Cut

        cuts = [
            Cut(start=0.0, end=1.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BEFORE_SPEECH),
            Cut(start=2.0, end=3.0, cut_type=CutType.FILLER, reason=CutReason.FILLER_WORD),
        ]

        keep_segments = compute_keep_segments(cuts, total_duration=5.0)

        assert len(keep_segments) == 2
        # First segment: 1.0 to 2.0
        assert keep_segments[0].start == 1.0
        assert keep_segments[0].end == 2.0
        # Second segment: 3.0 to 5.0
        assert keep_segments[1].start == 3.0
        assert keep_segments[1].end == 5.0

    def test_no_cuts(self):
        """Test with no cuts - entire file is kept."""
        keep_segments = compute_keep_segments([], total_duration=5.0)

        assert len(keep_segments) == 1
        assert keep_segments[0].start == 0.0
        assert keep_segments[0].end == 5.0

    def test_cut_at_beginning(self):
        """Test with cut at the beginning."""
        from derush.models import Cut

        cuts = [
            Cut(start=0.0, end=2.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_BEFORE_SPEECH),
        ]

        keep_segments = compute_keep_segments(cuts, total_duration=5.0)

        assert len(keep_segments) == 1
        assert keep_segments[0].start == 2.0
        assert keep_segments[0].end == 5.0

    def test_cut_at_end(self):
        """Test with cut at the end."""
        from derush.models import Cut

        cuts = [
            Cut(start=3.0, end=5.0, cut_type=CutType.SILENCE, reason=CutReason.GAP_AFTER_SPEECH),
        ]

        keep_segments = compute_keep_segments(cuts, total_duration=5.0)

        assert len(keep_segments) == 1
        assert keep_segments[0].start == 0.0
        assert keep_segments[0].end == 3.0


class TestRunPipelineValidation:
    """Tests for run_pipeline input validation."""

    def test_invalid_word_segment_raises_validation_error(self, tmp_path):
        """Malformed word segment (missing 'start') raises ValidationError with clear message."""
        import json

        from derush.cutter import run_pipeline
        from derush.exceptions import ValidationError

        bad_json = tmp_path / "bad.json"
        bad_json.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "end": 1.0},
                    ],
                    "language": "fr",
                }
            )
        )

        with pytest.raises(ValidationError, match="Invalid word segment.*'start'.*'end'"):
            run_pipeline(
                whisperx_path=bad_json,
                total_duration=10.0,
                language="fr",
            )

    def test_word_segments_built_from_segments_when_missing(self, tmp_path):
        """When word_segments is missing, it is built from segments[].words."""
        import json

        from derush.cutter import run_pipeline

        json_path = tmp_path / "from_segments.json"
        json_path.write_text(
            json.dumps(
                {
                    "segments": [
                        {
                            "start": 0.0,
                            "end": 1.0,
                            "text": "hi",
                            "words": [
                                {"word": "hi", "start": 0.0, "end": 1.0, "score": 0.9},
                            ],
                        },
                    ],
                    "language": "fr",
                }
            )
        )

        result = run_pipeline(
            whisperx_path=json_path,
            total_duration=2.0,
            language="fr",
        )
        assert result.total_words == 1
        assert result.words[0].word == "hi"
