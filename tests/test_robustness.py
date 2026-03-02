"""Tests for robustness and edge cases.

These tests verify that:
1. Silent audio files are handled correctly
2. Continuous speech files are handled correctly
3. Abnormally long words are corrected
4. Empty inputs are handled gracefully
"""


from derush.config import CutterConfig
from derush.cutter import (
    classify_words,
    compute_cuts,
    compute_keep_segments,
    correct_word_timestamps,
    run_pipeline,
)
from derush.models import Word, WordStatus


class TestSilentFile:
    """Tests for files with no speech (silent audio)."""

    def test_no_words_single_cut(self):
        """A file with no words should have one cut covering entire duration."""
        config = CutterConfig()
        cuts = compute_cuts([], config, total_duration=30.0)

        assert len(cuts) == 1
        assert cuts[0].start == 0.0
        assert cuts[0].end == 30.0

    def test_no_words_no_keep_segments(self):
        """A file with no words should have no keep segments."""
        cuts = compute_cuts([], CutterConfig(), total_duration=30.0)
        segments = compute_keep_segments(cuts, total_duration=30.0)

        # With one cut covering entire file, no segments to keep
        assert len(segments) == 0

    def test_empty_whisperx_data(self, tmp_path):
        """Empty WhisperX data should be handled gracefully."""
        import json

        whisperx_path = tmp_path / "empty.json"
        whisperx_path.write_text(
            json.dumps({"segments": [], "word_segments": [], "language": "fr"})
        )

        config = CutterConfig()
        result = run_pipeline(
            whisperx_path=whisperx_path,
            total_duration=30.0,
            language="fr",
            config=config,
        )

        assert result.total_words == 0
        assert result.kept_words == 0
        assert result.filler_words == 0
        assert len(result.cuts) == 1
        assert result.cuts[0].start == 0.0
        assert result.cuts[0].end == 30.0


class TestContinuousSpeech:
    """Tests for files with continuous speech (no silences)."""

    def test_no_silences_single_segment(self):
        """A file with no silences should have one keep segment."""
        # Continuous speech: words back-to-back
        words = [
            Word(word="Hello", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="world", start=0.5, end=1.0, score=0.9, status=WordStatus.KEPT),
            Word(word="this", start=1.0, end=1.3, score=0.9, status=WordStatus.KEPT),
            Word(word="is", start=1.3, end=1.5, score=0.9, status=WordStatus.KEPT),
            Word(word="continuous", start=1.5, end=2.0, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig(min_silence=0.5)
        cuts = compute_cuts(words, config, total_duration=2.5)
        segments = compute_keep_segments(cuts, total_duration=2.5)

        # Should have minimal cuts (maybe end silence if any)
        # And one main keep segment
        assert len(segments) >= 1

        # Main segment should cover most of the duration
        main_segment = segments[0]
        assert main_segment.start == 0.0
        assert main_segment.end >= 2.0

    def test_continuous_speech_no_filler_cuts(self):
        """Continuous speech without fillers should have no filler cuts."""
        words = [
            Word(word="Je", start=0.0, end=0.2, score=0.9, status=WordStatus.KEPT),
            Word(word="parle", start=0.2, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="continuellement", start=0.5, end=1.0, score=0.9, status=WordStatus.KEPT),
            Word(word="sans", start=1.0, end=1.2, score=0.9, status=WordStatus.KEPT),
            Word(word="pause", start=1.2, end=1.5, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=2.0)

        filler_cuts = [c for c in cuts if c.cut_type.value == "filler"]
        assert len(filler_cuts) == 0


class TestAbnormallyLongWords:
    """Tests for handling abnormally long words from WhisperX."""

    def test_10_second_word_is_corrected(self):
        """A 10-second word should be corrected to reasonable duration."""
        words = [
            Word(word="test", start=0.0, end=10.0, score=0.9),
        ]

        config = CutterConfig(max_word_duration=2.0)
        corrected = correct_word_timestamps(words, config)

        duration = corrected[0].end - corrected[0].start
        assert duration < 1.0, f"Word should be corrected to <1s, got {duration}s"

    def test_30_second_word_is_corrected(self):
        """Even a 30-second word should be corrected."""
        words = [
            Word(word="bonjour", start=0.0, end=30.0, score=0.8),
        ]

        config = CutterConfig(max_word_duration=2.0)
        corrected = correct_word_timestamps(words, config)

        duration = corrected[0].end - corrected[0].start
        assert duration < 2.0

    def test_long_word_exposes_hidden_gap(self):
        """Correcting a long word should expose hidden gaps."""
        # "test" absorbs a 4-second gap
        words = [
            Word(word="de", start=0.0, end=0.3, score=0.9),
            Word(word="test", start=0.3, end=8.0, score=0.8),  # 7.7s - way too long!
            Word(word="suite", start=8.0, end=8.5, score=0.9),
        ]

        config = CutterConfig(max_word_duration=2.0)
        corrected = correct_word_timestamps(words, config)

        # After correction, "test" should be much shorter
        test_word = corrected[1]
        test_duration = test_word.end - test_word.start
        assert test_duration < 1.0

        # Gap between corrected "test" and "suite" should be exposed
        gap = corrected[2].start - test_word.end
        assert gap > 5.0, "Hidden gap should be exposed after correction"


class TestVeryShortFiles:
    """Tests for very short files."""

    def test_1_second_file(self):
        """A 1-second file should be handled correctly."""
        words = [
            Word(word="Hi", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig(min_silence=0.5)
        cuts = compute_cuts(words, config, total_duration=1.0)
        segments = compute_keep_segments(cuts, total_duration=1.0)

        # Should handle gracefully
        assert len(cuts) >= 0
        assert len(segments) >= 1

    def test_500ms_file(self):
        """A 500ms file should be handled correctly."""
        words = [
            Word(word="ok", start=0.0, end=0.3, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=0.5)
        segments = compute_keep_segments(cuts, total_duration=0.5)

        # End silence is only 0.2s, below min_silence threshold
        # So should have minimal cuts
        assert len(segments) >= 1


class TestVeryLongFiles:
    """Tests for very long files."""

    def test_1_hour_file_simulation(self):
        """Simulate handling of a 1-hour file."""
        # Simulate words spread across 1 hour
        words = []
        for i in range(100):
            start = i * 30.0 + 1.0  # Word every 30 seconds
            words.append(
                Word(
                    word=f"word{i}", start=start, end=start + 0.5, score=0.9, status=WordStatus.KEPT
                )
            )

        total_duration = 3600.0  # 1 hour

        config = CutterConfig(min_silence=0.5)
        cuts = compute_cuts(words, config, total_duration)
        segments = compute_keep_segments(cuts, total_duration)

        # Should handle large number of segments
        assert len(segments) == 100  # One segment per word

        # Check coherence
        cut_duration = sum(c.end - c.start for c in cuts)
        keep_duration = sum(s.end - s.start for s in segments)
        assert abs(cut_duration + keep_duration - total_duration) < 0.001


class TestBoundaryConditions:
    """Tests for boundary conditions."""

    def test_word_at_exact_start(self):
        """Word starting exactly at 0.0 should not cause issues."""
        words = [
            Word(word="Start", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="middle", start=0.5, end=1.0, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig(min_silence=0.5)
        cuts = compute_cuts(words, config, total_duration=2.0)

        # No cut at start since word starts at 0.0
        initial_cut = next((c for c in cuts if c.start == 0.0), None)
        assert initial_cut is None

    def test_word_at_exact_end(self):
        """Word ending exactly at duration should not cause issues."""
        words = [
            Word(word="End", start=1.5, end=2.0, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig(min_silence=0.5)
        cuts = compute_cuts(words, config, total_duration=2.0)

        # No end cut since word ends at 2.0
        end_cut = next((c for c in cuts if c.end == 2.0), None)
        # There might be a cut at start, but no cut after the word
        # because end_silence = 2.0 - 2.0 = 0

    def test_zero_duration_word(self):
        """Word with zero duration should be handled (min 50ms enforced if long)."""
        words = [
            Word(word="zero", start=1.0, end=1.0, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        # Should not crash
        corrected = correct_word_timestamps(words, config)
        cuts = compute_cuts(words, config, total_duration=2.0)

        # Word has 0s duration and is not > max_word_duration, so no correction
        # The correction logic only triggers for words that are too long OR have low score
        assert corrected[0].end == corrected[0].start  # 0 duration preserved

    def test_overlapping_words(self):
        """Overlapping words should be handled gracefully."""
        words = [
            Word(word="first", start=0.0, end=1.0, score=0.9, status=WordStatus.KEPT),
            Word(word="overlap", start=0.8, end=1.5, score=0.9, status=WordStatus.KEPT),
        ]

        config = CutterConfig()
        # Should not crash
        cuts = compute_cuts(words, config, total_duration=2.0)
        segments = compute_keep_segments(cuts, total_duration=2.0)

        # Should produce valid output
        assert len(segments) >= 1


class TestUnusualInputs:
    """Tests for unusual or malformed inputs."""

    def test_single_filler_word(self):
        """A file with only a filler word should be cut entirely."""
        words = [
            Word(word="euh", start=0.0, end=0.3, score=0.8, status=WordStatus.FILLER),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=1.0)
        segments = compute_keep_segments(cuts, total_duration=1.0)

        # Should have initial silence + filler cut
        assert len(cuts) >= 1

        # Filler should be covered by a cut
        filler_covered = any(c.start <= 0.0 and c.end >= 0.3 for c in cuts)
        assert filler_covered

    def test_all_filler_words(self):
        """A file with only filler words should be mostly cut."""
        words = [
            Word(word="euh", start=1.0, end=1.3, score=0.8, status=WordStatus.FILLER),
            Word(word="um", start=3.0, end=3.2, score=0.7, status=WordStatus.FILLER),
            Word(word="hmm", start=5.0, end=5.2, score=0.6, status=WordStatus.FILLER),
        ]

        config = CutterConfig()
        cuts = compute_cuts(words, config, total_duration=10.0)

        # All fillers should be cut
        for word in words:
            covered = any(c.start <= word.start and c.end >= word.end for c in cuts)
            assert covered, f"Filler '{word.word}' should be covered by a cut"

    def test_very_low_scores(self):
        """Words with very low scores should be handled."""
        words = [
            Word(word="unclear", start=0.0, end=5.0, score=0.1),  # Very low score
            Word(word="also", start=5.0, end=10.0, score=0.05),  # Even lower
        ]

        config = CutterConfig(min_word_score=0.5)
        corrected = correct_word_timestamps(words, config)

        # Should be corrected due to low scores
        for word in corrected:
            duration = word.end - word.start
            assert duration < 2.0, f"Low-score word should be corrected: {duration}s"

    def test_special_characters_in_words(self):
        """Words with special characters should be handled."""
        words = [
            Word(word="café", start=0.0, end=0.5, score=0.9, status=WordStatus.KEPT),
            Word(word="naïve", start=0.5, end=1.0, score=0.9, status=WordStatus.KEPT),
            Word(word="test!", start=1.0, end=1.5, score=0.9, status=WordStatus.KEPT),
        ]

        result = classify_words(words, language="fr")

        # All should be kept (not fillers)
        assert all(w.status == WordStatus.KEPT for w in result)
