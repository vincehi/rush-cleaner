"""Tests for cutter module V2."""

import json

import pytest

from derush.cutter import (
    _build_filler_patterns,
    _normalize_word,
    build_timeline,
    classify_words,
    correct_word_timestamps,
    estimate_word_duration,
    filter_kept_words,
    is_filler,
    merge_adjacent_tokens,
    run_pipeline,
)
from derush.models import (
    TimelineToken,
    Word,
    WordStatus,
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


class TestEstimateWordDuration:
    """Tests for estimate_word_duration function."""

    def test_short_words(self):
        """Short words (1-2 letters) get minimum duration."""
        assert estimate_word_duration("le") == 0.15
        assert estimate_word_duration("de") == 0.15
        assert estimate_word_duration("a") == 0.15

    def test_three_letter_words(self):
        """3-letter words get slightly longer duration."""
        assert estimate_word_duration("pas") == 0.20
        assert estimate_word_duration("cas") == 0.20

    def test_medium_words(self):
        """4-5 letter words get medium duration."""
        assert estimate_word_duration("test") == 0.35
        # "voiture" has 7 letters -> 6-8 category
        assert estimate_word_duration("voiture") == 0.55

    def test_longer_words(self):
        """6-8 letter words get longer duration."""
        # "maintenant" has 10 letters -> 9+ category
        assert estimate_word_duration("maintenant") == 0.8
        # "manger" has 6 letters -> 6-8 category
        assert estimate_word_duration("manger") == 0.55

    def test_very_long_words(self):
        """Very long words are capped at max duration."""
        # 20 chars * 0.08 = 1.6s, but capped at 1.5s
        assert estimate_word_duration("anticonstitutionnellement") == 1.5


class TestCorrectWordTimestamps:
    """Tests for correct_word_timestamps function."""

    def test_no_correction_needed(self):
        """Words with normal duration are not corrected."""
        # Use words with durations that don't exceed their expected max
        # "bonjour" (7 letters) max = 0.55s, duration 0.5s is OK
        # "monde" (5 letters) max = 0.35s, duration 0.3s is OK
        words = [
            Word(word="bonjour", start=0.0, end=0.5, score=0.9),
            Word(word="monde", start=0.6, end=0.9, score=0.9),
        ]
        corrected, count = correct_word_timestamps(words)
        assert count == 0
        assert len(corrected) == 2

    def test_abnormally_long_word_corrected(self):
        """Words with abnormally long duration are truncated."""
        # "test" (4 letters) should be ~0.35s max
        words = [
            Word(word="test", start=0.0, end=5.0, score=0.9),  # 5s = way too long
        ]
        corrected, count = correct_word_timestamps(words)
        assert count == 1
        assert corrected[0].end < 1.0  # Should be truncated to ~0.35s

    def test_respects_next_word_boundary(self):
        """Corrected end time doesn't extend past next word start."""
        words = [
            Word(word="test", start=0.0, end=5.0, score=0.9),
            Word(word="next", start=0.3, end=0.5, score=0.9),  # Next word starts at 0.3
        ]
        corrected, count = correct_word_timestamps(words)
        assert corrected[0].end < 0.3  # Should not extend past next word


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


class TestFilterKeptWords:
    """Tests for filter_kept_words function."""

    def test_filter_removes_fillers(self):
        """Filler words are removed from the list."""
        words = [
            Word(word="hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="um", start=0.5, end=0.7, score=0.8, status=WordStatus.FILLER),
            Word(word="world", start=0.7, end=1.0, score=0.9, status=WordStatus.KEPT),
        ]

        kept = filter_kept_words(words)

        assert len(kept) == 2
        assert kept[0].word == "hello"
        assert kept[1].word == "world"

    def test_filter_keeps_all_when_no_fillers(self):
        """All words kept when no fillers."""
        words = [
            Word(word="hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="world", start=0.5, end=1.0, score=0.9, status=WordStatus.KEPT),
        ]

        kept = filter_kept_words(words)

        assert len(kept) == 2


class TestBuildTimeline:
    """Tests for build_timeline function."""

    def test_continuous_timeline(self):
        """Timeline tokens have continuous positions."""
        words = [
            Word(word="hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="world", start=0.6, end=1.0, score=0.9, status=WordStatus.KEPT),
        ]

        tokens = build_timeline(words)

        assert len(tokens) == 2
        # First token starts at 0
        assert tokens[0].timeline_start == 0.0
        assert tokens[0].timeline_end == 0.5
        # Second token continues immediately
        assert tokens[1].timeline_start == 0.5
        assert tokens[1].timeline_end == 0.9

    def test_original_positions_preserved(self):
        """Original positions in source are preserved."""
        words = [
            Word(word="hello", start=1.0, end=1.5, score=0.9, status=WordStatus.KEPT),
        ]

        tokens = build_timeline(words)

        assert tokens[0].original_start == 1.0
        assert tokens[0].original_end == 1.5


class TestMergeAdjacentTokens:
    """Tests for merge_adjacent_tokens function."""

    def test_single_token(self):
        """Single token becomes single segment."""
        tokens = [
            TimelineToken(
                text="hello",
                original_start=0.0,
                original_end=0.5,
                timeline_start=0.0,
                timeline_end=0.5,
            ),
        ]

        segments = merge_adjacent_tokens(tokens)

        assert len(segments) == 1
        assert segments[0].original_start == 0.0
        assert segments[0].original_end == 0.5

    def test_adjacent_tokens_merged(self):
        """Tokens with small gap in source are merged."""
        tokens = [
            TimelineToken(
                text="hello",
                original_start=0.0,
                original_end=0.5,
                timeline_start=0.0,
                timeline_end=0.5,
            ),
            TimelineToken(
                text="world",
                original_start=0.52,  # 0.02s gap - should be merged
                original_end=1.0,
                timeline_start=0.5,
                timeline_end=0.98,
            ),
        ]

        segments = merge_adjacent_tokens(tokens, max_gap=0.05)

        assert len(segments) == 1
        assert segments[0].original_start == 0.0
        assert segments[0].original_end == 1.0

    def test_distant_tokens_separate(self):
        """Tokens with large gap in source stay separate."""
        tokens = [
            TimelineToken(
                text="hello",
                original_start=0.0,
                original_end=0.5,
                timeline_start=0.0,
                timeline_end=0.5,
            ),
            TimelineToken(
                text="world",
                original_start=1.0,  # 0.5s gap - should NOT be merged
                original_end=1.5,
                timeline_start=0.5,
                timeline_end=1.0,
            ),
        ]

        segments = merge_adjacent_tokens(tokens, max_gap=0.05)

        assert len(segments) == 2


class TestRunPipeline:
    """Tests for run_pipeline function."""

    def test_basic_pipeline(self, tmp_path):
        """Basic pipeline produces expected results."""
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "start": 0.0, "end": 0.5, "score": 0.9},
                        {"word": "world", "start": 0.6, "end": 1.0, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=2.0,
            language="en",
        )

        assert result.total_words == 2
        assert result.kept_words == 2
        assert result.filler_words == 0
        assert len(result.keep_segments) >= 1

    def test_filler_removed(self, tmp_path):
        """Filler words are removed from keep segments."""
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "start": 0.0, "end": 0.5, "score": 0.9},
                        {"word": "um", "start": 0.5, "end": 0.7, "score": 0.8},
                        {"word": "world", "start": 0.7, "end": 1.0, "score": 0.9},
                    ],
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=2.0,
            language="en",
        )

        assert result.total_words == 3
        assert result.kept_words == 2
        assert result.filler_words == 1

    def test_invalid_word_segment_raises_validation_error(self, tmp_path):
        """Malformed word segment raises ValidationError."""
        from derush.exceptions import ValidationError

        whisperx_path = tmp_path / "bad.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "end": 1.0},  # Missing 'start'
                    ],
                }
            )
        )

        with pytest.raises(ValidationError, match="Invalid WhisperX format"):
            run_pipeline(
                whisperx_path=whisperx_path,
                total_duration=10.0,
                language="fr",
            )

    def test_word_segments_built_from_segments_when_missing(self, tmp_path):
        """When word_segments is missing, it is built from segments[].words."""
        whisperx_path = tmp_path / "from_segments.json"
        whisperx_path.write_text(
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
                }
            )
        )

        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=2.0,
            language="en",
        )

        assert result.total_words == 1
        assert result.words[0].word == "hi"

    def test_debug_output(self, tmp_path):
        """Debug output creates expected files."""
        whisperx_path = tmp_path / "test.json"
        whisperx_path.write_text(
            json.dumps(
                {
                    "word_segments": [
                        {"word": "hello", "start": 0.0, "end": 0.5, "score": 0.9},
                    ],
                }
            )
        )

        debug_base = tmp_path / "debug"

        run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=2.0,
            language="en",
            debug_output=debug_base,
        )

        # Check debug files exist
        assert (tmp_path / "debug.1_loaded.json").exists()
        assert (tmp_path / "debug.2_corrected.json").exists()
        assert (tmp_path / "debug.3_classified.json").exists()
        assert (tmp_path / "debug.4_filtered.json").exists()
        assert (tmp_path / "debug.5_timeline.json").exists()
        assert (tmp_path / "debug.6_segments.json").exists()
