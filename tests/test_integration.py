"""Integration tests for the cutting pipeline.

These tests verify that:
1. Timestamps in outputs are consistent with WhisperX
2. Fillers and silences are correctly cut
3. Keep segments are coherent (no gaps, no overlaps)
4. EDL and FCPXML contain correct timecodes
5. Snapshot tests ensure stability
"""

import json
from pathlib import Path

import pytest

from src.config import CutterConfig
from src.cutter import run_pipeline
from src.exporters.edl import EDLExporter
from src.exporters.fcpxml import FCPXMLExporter
from src.exporters.json import JSONExporter
from src.media_info import MediaInfo


# Fixtures
@pytest.fixture
def whisperx_data():
    """Load the sample WhisperX data."""
    whisperx_path = Path("output/sample_whisperx.json")
    if not whisperx_path.exists():
        pytest.skip("WhisperX output not found")
    with open(whisperx_path) as f:
        return json.load(f)


@pytest.fixture
def media_info():
    """Create media info for the sample video."""
    video_path = Path("tests/fixtures/sample.mov")
    if not video_path.exists():
        pytest.skip("Sample video not found")
    from src.media_info import get_media_info
    return get_media_info(video_path)


@pytest.fixture
def cutter_result(media_info):
    """Run the cutting pipeline."""
    whisperx_path = Path("output/sample_whisperx.json")
    if not whisperx_path.exists():
        pytest.skip("WhisperX output not found")

    config = CutterConfig()
    return run_pipeline(
        whisperx_path=whisperx_path,
        total_duration=media_info.duration,
        language="fr",
        config=config,
    )


class TestSnapshotSample:
    """Snapshot tests to ensure pipeline output stability."""

    def test_total_words_count(self, cutter_result):
        """Total words should be 14."""
        assert cutter_result.total_words == 14

    def test_kept_words_count(self, cutter_result):
        """Kept words should be 13."""
        assert cutter_result.kept_words == 13

    def test_filler_words_count(self, cutter_result):
        """Filler words should be 1."""
        assert cutter_result.filler_words == 1

    def test_cut_percentage(self, cutter_result):
        """Cut percentage should be ~63%."""
        assert 58 < cutter_result.cut_percentage < 68

    def test_keep_segments_count(self, cutter_result):
        """Should have 4 keep segments."""
        assert len(cutter_result.keep_segments) == 4

    def test_cuts_count(self, cutter_result):
        """Should have 4 cuts."""
        assert len(cutter_result.cuts) == 4

    def test_original_duration(self, cutter_result, media_info):
        """Original duration should match media info."""
        assert abs(cutter_result.original_duration - media_info.duration) < 0.01

    def test_final_duration_approximate(self, cutter_result):
        """Final duration should be approximately 6.2 seconds."""
        assert 6.0 < cutter_result.final_duration < 6.5


class TestSpecificTimestamps:
    """Tests for specific timestamp values from sample."""

    def test_keep1_timestamps(self, cutter_result):
        """Keep 1: 1.6 → 4.588s (contains 'petite démo de test')."""
        seg = cutter_result.keep_segments[0]
        assert abs(seg.start - 1.6) < 0.1
        assert abs(seg.end - 4.588) < 0.1

    def test_keep2_timestamps(self, cutter_result):
        """Keep 2: 8.742 → 9.524s (contains 'je pense que')."""
        seg = cutter_result.keep_segments[1]
        assert abs(seg.start - 8.742) < 0.1
        assert abs(seg.end - 9.524) < 0.1

    def test_keep3_timestamps(self, cutter_result):
        """Keep 3: 12.153 → 12.775s (contains 'voilà')."""
        seg = cutter_result.keep_segments[2]
        assert abs(seg.start - 12.153) < 0.1
        assert abs(seg.end - 12.775) < 0.1

    def test_keep4_timestamps(self, cutter_result, media_info):
        """Keep 4: 14.999 → end (contains 'de quoi par le ton')."""
        seg = cutter_result.keep_segments[3]
        assert abs(seg.start - 14.999) < 0.1
        assert abs(seg.end - media_info.duration) < 0.1


class TestAntiRegression:
    """Anti-regression tests to prevent specific issues."""

    def test_test_word_never_exceeds_1s(self, cutter_result):
        """REGRESSION: 'test' must NEVER exceed 1s after correction."""
        test_word = next((w for w in cutter_result.words if w.word == "test"), None)
        assert test_word is not None
        duration = test_word.end - test_word.start
        assert duration < 1.0, f"'test' duration {duration}s exceeds 1s"

    def test_hmm_is_in_cut(self, cutter_result):
        """REGRESSION: 'hmm' must ALWAYS be in a cut."""
        hmm_word = next((w for w in cutter_result.words if w.word == "hmm"), None)
        assert hmm_word is not None
        assert hmm_word.status.value == "filler"

        # Check hmm is covered by a cut
        covered = any(
            cut.start <= hmm_word.start and cut.end >= hmm_word.end
            for cut in cutter_result.cuts
        )
        assert covered, "'hmm' should be covered by a cut"

    def test_voilà_is_kept(self, cutter_result):
        """REGRESSION: 'voilà' must NEVER be in a cut."""
        voila_word = next((w for w in cutter_result.words if w.word == "voilà"), None)
        assert voila_word is not None
        assert voila_word.status.value == "kept"

        # Check voilà is NOT covered by any cut
        in_cut = any(
            cut.start <= voila_word.start and cut.end >= voila_word.end
            for cut in cutter_result.cuts
        )
        assert not in_cut, "'voilà' should NOT be in a cut"

    def test_quoi_is_kept(self, cutter_result):
        """REGRESSION: 'quoi' must NEVER be in a cut."""
        quoi_word = next((w for w in cutter_result.words if w.word == "quoi"), None)
        assert quoi_word is not None
        assert quoi_word.status.value == "kept"


class TestPipelineConsistency:
    """Tests for pipeline output consistency."""

    def test_all_words_classified(self, cutter_result, whisperx_data):
        """All words from WhisperX should be classified."""
        whisperx_words = whisperx_data.get("word_segments", [])
        assert len(cutter_result.words) == len(whisperx_words)

    def test_filler_words_detected_correctly(self, cutter_result):
        """Known filler words should be detected."""
        filler_words = [w.word.lower() for w in cutter_result.words if w.status.value == "filler"]

        # "hmm" should always be detected as filler
        assert "hmm" in filler_words, "hmm should be detected as filler"

    def test_content_words_not_cut(self, cutter_result):
        """Content words should not be in filler list."""
        content_words = [w.word.lower() for w in cutter_result.words if w.status.value == "kept"]

        # These should be kept
        expected_kept = ["petite", "démo", "de", "test", "je", "pense", "que", "par", "le", "ton"]
        for word in expected_kept:
            assert word in content_words, f"'{word}' should be kept"

    def test_cuts_cover_all_fillers(self, cutter_result):
        """All filler words should be covered by cuts."""
        filler_words = [w for w in cutter_result.words if w.status.value == "filler"]

        for filler in filler_words:
            # Check if this filler is covered by at least one cut
            covered = any(
                cut.start <= filler.start and cut.end >= filler.end
                for cut in cutter_result.cuts
            )
            assert covered, f"Filler '{filler.word}' at [{filler.start}, {filler.end}] is not covered by any cut"


class TestKeepSegmentsCoherence:
    """Tests for keep segments coherence."""

    def test_no_overlapping_keep_segments(self, cutter_result):
        """Keep segments should not overlap."""
        segments = sorted(cutter_result.keep_segments, key=lambda s: s.start)

        for i in range(len(segments) - 1):
            current = segments[i]
            next_seg = segments[i + 1]
            assert current.end <= next_seg.start, \
                f"Segments overlap: [{current.start}, {current.end}] and [{next_seg.start}, {next_seg.end}]"

    def test_no_gaps_in_timeline(self, cutter_result, media_info):
        """Keep segments + cuts should cover the entire timeline."""
        total_duration = media_info.duration

        # Combine all time ranges
        all_ranges = []
        for seg in cutter_result.keep_segments:
            all_ranges.append((seg.start, seg.end, "keep"))
        for cut in cutter_result.cuts:
            all_ranges.append((cut.start, cut.end, "cut"))

        # Sort by start time
        all_ranges.sort(key=lambda x: x[0])

        # Check for gaps
        current_end = 0.0
        for start, end, type_ in all_ranges:
            if start > current_end + 0.001:  # Allow small floating point errors
                pytest.fail(f"Gap detected in timeline: [{current_end}, {start}] is not covered")
            current_end = max(current_end, end)

        # Check that we reach the end
        assert abs(current_end - total_duration) < 0.01, \
            f"Timeline doesn't reach end: {current_end} vs {total_duration}"

    def test_keep_segments_dont_contain_fillers(self, cutter_result):
        """Keep segments should not contain filler words."""
        filler_words = [w for w in cutter_result.words if w.status.value == "filler"]

        for filler in filler_words:
            for seg in cutter_result.keep_segments:
                # Filler should not be fully contained in a keep segment
                contained = seg.start <= filler.start and seg.end >= filler.end
                assert not contained, \
                    f"Filler '{filler.word}' [{filler.start}, {filler.end}] is inside keep segment [{seg.start}, {seg.end}]"

    def test_total_keep_duration_matches_summary(self, cutter_result):
        """Sum of keep segment durations should match final_duration."""
        total_keep = sum(seg.duration for seg in cutter_result.keep_segments)
        assert abs(total_keep - cutter_result.final_duration) < 0.001, \
            f"Keep segments total {total_keep} doesn't match final_duration {cutter_result.final_duration}"


class TestCutCalculation:
    """Tests for cut calculation correctness."""

    def test_initial_silence_cut(self, cutter_result, whisperx_data):
        """Initial silence (before first word) should be cut if >= min_silence."""
        word_segments = whisperx_data.get("word_segments", [])
        if not word_segments:
            pytest.skip("No words in WhisperX data")

        first_word_start = word_segments[0]["start"]

        if first_word_start >= 0.5:  # min_silence default
            # Should have a cut at the beginning
            initial_cut = next(
                (c for c in cutter_result.cuts if c.start == 0.0),
                None
            )
            assert initial_cut is not None, "Missing cut for initial silence"
            assert initial_cut.end == first_word_start, \
                f"Initial cut should end at {first_word_start}, not {initial_cut.end}"

    def test_cuts_are_sorted(self, cutter_result):
        """Cuts should be sorted by start time."""
        starts = [c.start for c in cutter_result.cuts]
        assert starts == sorted(starts), "Cuts are not sorted by start time"

    def test_cuts_dont_overlap(self, cutter_result):
        """Cuts should not overlap (after merging)."""
        cuts = sorted(cutter_result.cuts, key=lambda c: c.start)

        for i in range(len(cuts) - 1):
            current = cuts[i]
            next_cut = cuts[i + 1]
            assert current.end <= next_cut.start, \
                f"Cuts overlap: [{current.start}, {current.end}] and [{next_cut.start}, {next_cut.end}]"


class TestEDLOutput:
    """Tests for EDL output correctness."""

    def test_edl_events_match_cuts(self, cutter_result, media_info, tmp_path):
        """EDL should have one event per cut."""
        edl_path = tmp_path / "test.edl"

        exporter = EDLExporter()
        exporter.export(cutter_result, media_info, edl_path)

        content = edl_path.read_text()

        # Count event lines (lines starting with 001, 002, etc.)
        event_lines = [l for l in content.split("\n") if l.strip() and l[0:3].isdigit()]

        assert len(event_lines) == len(cutter_result.cuts), \
            f"EDL has {len(event_lines)} events but there are {len(cutter_result.cuts)} cuts"

    def test_edl_timecodes_are_valid(self, cutter_result, media_info, tmp_path):
        """EDL timecodes should be valid (within video duration)."""
        edl_path = tmp_path / "test.edl"

        exporter = EDLExporter()
        exporter.export(cutter_result, media_info, edl_path)

        content = edl_path.read_text()
        max_frames = int(media_info.duration * media_info.fps)

        # Parse timecodes from EDL (format: HH:MM:SS:FF)
        import re
        timecode_pattern = r"(\d{2}):(\d{2}):(\d{2}):(\d{2})"
        timecodes = re.findall(timecode_pattern, content)

        for hours, minutes, seconds, frames in timecodes:
            total_frames = (
                int(hours) * 3600 * int(media_info.fps) +
                int(minutes) * 60 * int(media_info.fps) +
                int(seconds) * int(media_info.fps) +
                int(frames)
            )
            assert total_frames <= max_frames + int(media_info.fps), \
                f"Timecode {hours}:{minutes}:{seconds}:{frames} exceeds video duration"


class TestFCPXMLOutput:
    """Tests for FCPXML output correctness."""

    def test_fcpxml_clips_match_keep_segments(self, cutter_result, media_info, tmp_path):
        """FCPXML should have one asset-clip per keep segment."""
        fcpxml_path = tmp_path / "test.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(cutter_result, media_info, fcpxml_path)

        content = fcpxml_path.read_text()

        # Count asset-clip elements
        import re
        clip_count = len(re.findall(r"<asset-clip", content))

        assert clip_count == len(cutter_result.keep_segments), \
            f"FCPXML has {clip_count} clips but there are {len(cutter_result.keep_segments)} keep segments"

    def test_fcpxml_sequence_duration(self, cutter_result, media_info, tmp_path):
        """FCPXML sequence duration should match final_duration."""
        fcpxml_path = tmp_path / "test.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(cutter_result, media_info, fcpxml_path)

        content = fcpxml_path.read_text()

        # Find sequence duration attribute
        import re
        match = re.search(r'sequence[^>]*duration="(\d+)/(\d+)s"', content)
        if match:
            numerator = int(match.group(1))
            denominator = int(match.group(2))
            sequence_duration = numerator / denominator

            # Allow small floating point difference
            assert abs(sequence_duration - cutter_result.final_duration) < 0.1, \
                f"Sequence duration {sequence_duration}s doesn't match final_duration {cutter_result.final_duration}s"

    def test_fcpxml_asset_path_exists(self, cutter_result, media_info, tmp_path):
        """FCPXML asset src should point to existing file."""
        fcpxml_path = tmp_path / "test.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(cutter_result, media_info, fcpxml_path)

        content = fcpxml_path.read_text()

        # Extract file path from src attribute
        import re
        match = re.search(r'src="file://([^"]+)"', content)
        if match:
            file_path = match.group(1)
            assert Path(file_path).exists(), f"Asset file does not exist: {file_path}"


class TestJSONOutput:
    """Tests for JSON output correctness."""

    def test_json_contains_all_words(self, cutter_result, media_info, tmp_path):
        """JSON should contain all words with their status."""
        json_path = tmp_path / "test.json"

        exporter = JSONExporter()
        exporter.export(cutter_result, media_info, json_path)

        with open(json_path) as f:
            data = json.load(f)

        assert len(data["words"]["list"]) == cutter_result.total_words

    def test_json_summary_is_correct(self, cutter_result, media_info, tmp_path):
        """JSON summary should match CutterResult."""
        json_path = tmp_path / "test.json"

        exporter = JSONExporter()
        exporter.export(cutter_result, media_info, json_path)

        with open(json_path) as f:
            data = json.load(f)

        summary = data["summary"]
        assert summary["original_duration"] == round(cutter_result.original_duration, 3)
        assert summary["final_duration"] == round(cutter_result.final_duration, 3)
        assert summary["fillers_cut"] == cutter_result.filler_words

    def test_json_cuts_match_result(self, cutter_result, media_info, tmp_path):
        """JSON cuts should match CutterResult cuts."""
        json_path = tmp_path / "test.json"

        exporter = JSONExporter()
        exporter.export(cutter_result, media_info, json_path)

        with open(json_path) as f:
            data = json.load(f)

        assert len(data["cuts"]) == len(cutter_result.cuts)

        for json_cut, result_cut in zip(data["cuts"], sorted(cutter_result.cuts, key=lambda c: c.start)):
            assert json_cut["start"] == result_cut.start
            assert json_cut["end"] == result_cut.end
