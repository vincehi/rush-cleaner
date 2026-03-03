"""Tests for exporter modules."""

import json

import pytest
from lxml import etree

from derush.exporters.base import BaseExporter
from derush.exporters.fcpxml import FCPXMLExporter
from derush.exporters.json import JSONExporter
from derush.models import MediaInfo


class TestBaseExporter:
    """Tests for BaseExporter class."""

    def test_sort_cuts_chronologically(self, sample_cuts):
        """Test that cuts are sorted by start time."""
        sorted_cuts = BaseExporter.sort_cuts_chronologically(sample_cuts)

        assert sorted_cuts[0].start == 2.0
        assert sorted_cuts[1].start == 5.0
        assert sorted_cuts[2].start == 15.0


class TestFCPXMLExporter:
    """Tests for FCPXMLExporter class."""

    def test_export_creates_valid_xml(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that FCPXML export creates a valid XML file."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        assert output_path.exists()

        # Parse XML to validate structure
        tree = etree.parse(output_path)
        root = tree.getroot()

        assert root.tag == "fcpxml"
        assert root.get("version") == "1.9"

    def test_export_includes_resources(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that FCPXML includes resources section."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        resources = root.find("resources")
        assert resources is not None

        # Should have format and asset
        format_el = resources.find("format")
        asset_el = resources.find("asset")

        assert format_el is not None
        assert asset_el is not None

    def test_export_creates_keep_segments(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that FCPXML exports clips from KEPT word groups."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        # Find all asset-clips in spine
        # Token-based approach: clips are generated from consecutive KEPT word groups
        # Words: "Hello"(0.0-0.5) + "world"(0.6-1.0) → Group 1: [0.0-1.0]
        # Word: "content"(3.2-3.5) → Group 2: [3.2-3.5]
        # Word: "here"(4.0-4.5) → Group 3: [4.0-4.5]
        # Word: "final"(20.0-20.5) + "words"(20.6-21.0) → Group 4: [20.0-21.0]
        # Total: 4 clips (FILLER "euh" at 15.0-15.3 is skipped)
        asset_clips = root.xpath("//asset-clip")

        assert len(asset_clips) == 4, f"Expected 4 clips from word groups, got {len(asset_clips)}"

        # Check that first clip is "Keep 1" and all refs point to r2
        assert asset_clips[0].get("name") == "Keep 1"
        refs = {c.get("ref") for c in asset_clips}
        assert refs == {"r2"}

    def test_export_keep_segments_chronological(
        self, tmp_path, sample_cutter_result, sample_media_info
    ):
        """Test that keep segments are in chronological order on timeline."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        # Find asset-clips in spine
        clips = root.xpath("//spine/asset-clip")

        # First clip should start at offset 0 (format: "0/25s" for 25fps)
        assert clips is not None and len(clips) > 0
        offset = clips[0].get("offset")
        # Accept both "0s" and "0/Xs" format (rational time)
        assert offset == "0s" or offset.startswith("0/")

    def test_export_no_timeline_discontinuities(
        self, tmp_path, sample_cutter_result, sample_media_info
    ):
        """Test that there are no gaps between clips on timeline (no rounding errors)."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        # Find asset-clips in spine (one per segment)
        clips = root.xpath("//spine/asset-clip")

        # Parse rational time values
        def parse_rational(time_str):
            # Format: "num/dens" (e.g., "100/2500s")
            value = time_str.rstrip("s")
            if "/" in value:
                num, den = map(int, value.split("/"))
                return num, den
            # Simple seconds value - convert to rational with denominator 1
            return int(float(value)), 1

        # Check continuity between consecutive clips on timeline
        for i in range(len(clips) - 1):
            current = clips[i]
            next_clip = clips[i + 1]

            offset = parse_rational(current.get("offset"))
            dur = parse_rational(current.get("duration"))
            next_offset = parse_rational(next_clip.get("offset"))

            # offset + duration should equal next clip's offset
            end_num = offset[0] * dur[1] + dur[0] * offset[1]
            end_den = offset[1] * dur[1]

            expected_num = end_num * next_offset[1]
            actual_num = next_offset[0] * end_den

            assert expected_num == actual_num, (
                f"Discontinuity between segment {i + 1} and {i + 2}: {current.get('offset')} + {current.get('duration')} != {next_clip.get('offset')}"
            )

    def test_export_rational_fps(self, tmp_path, sample_cutter_result):
        """Test that rational FPS is used correctly."""
        media_info = MediaInfo(
            fps=29.97,
            fps_rational="30000/1001",
            duration=60.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4",
        )

        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        # Check format frameDuration
        format_el = root.xpath("//format")[0]
        frame_duration = format_el.get("frameDuration")

        # Should be in format "1001/30000s" (inverted from fps_rational)
        assert "1001/30000s" in frame_duration

    def test_export_asset_duration_uses_nb_frames_when_present(
        self, tmp_path, sample_cutter_result
    ):
        """When MediaInfo has nb_frames, asset duration in FCPXML is frame-based (avoids media offline)."""
        media_info = MediaInfo(
            fps=25.0,
            fps_rational="25/1",
            duration=20.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4",
            nb_frames=473,
        )
        output_path = tmp_path / "output.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, media_info, output_path)

        tree = etree.parse(output_path)
        asset = tree.xpath("//asset")[0]
        duration_str = asset.get("duration")
        # 473 frames at 25fps -> 473/25s
        assert duration_str == "473/25s"

    def test_export_no_clip_exceeds_asset_duration(
        self, tmp_path, sample_cutter_result, sample_media_info
    ):
        """No asset-clip must have start+duration > asset duration (prevents media offline)."""
        output_path = tmp_path / "output.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        tree = etree.parse(output_path)
        asset = tree.xpath("//asset")[0]
        clips = tree.xpath("//spine/asset-clip")

        def parse_rational(s):
            s = s.rstrip("s")
            if "/" in s:
                num, den = map(int, s.split("/"))
                return num, den
            return int(float(s)), 1

        asset_num, asset_den = parse_rational(asset.get("duration"))
        for clip in clips:
            start_num, start_den = parse_rational(clip.get("start"))
            dur_num, dur_den = parse_rational(clip.get("duration"))
            # clip end = start + duration (as rationals)
            end_num = start_num * dur_den + dur_num * start_den
            end_den = start_den * dur_den
            # end <= asset_duration  <=>  end_num * asset_den <= asset_num * end_den
            assert end_num * asset_den <= asset_num * end_den, (
                f"Clip {clip.get('name')} exceeds asset: "
                f"start={clip.get('start')} duration={clip.get('duration')} asset duration={asset.get('duration')}"
            )

    def test_export_clamps_and_skips_segments_past_asset_end(self, tmp_path):
        """When nb_frames limits the asset, clips past the end are skipped."""
        media_info = MediaInfo(
            fps=25.0,
            fps_rational="25/1",
            duration=60.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4",
            nb_frames=75,  # 75 frames = 3 seconds
        )
        # With token-based approach, clips are generated from words
        # Words at [0.0-1.0] fit, words at [10.0-12.0] are past the asset end
        from derush.models import Word, WordStatus, CutterResult, KeepSegment

        result = CutterResult(
            words=[
                Word(word="hello", start=0.0, end=1.0, score=0.9, status=WordStatus.KEPT),
                Word(word="world", start=10.0, end=12.0, score=0.9, status=WordStatus.KEPT),
            ],
            cuts=[],
            keep_segments=[
                KeepSegment(start=0.0, end=2.0),
                KeepSegment(start=10.0, end=12.0),
            ],
            total_words=2,
            kept_words=2,
            filler_words=0,
            corrected_words=0,
            original_duration=60.0,
            final_duration=4.0,
            cut_duration=56.0,
        )
        output_path = tmp_path / "output.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(result, media_info, output_path)

        tree = etree.parse(output_path)
        clips = tree.xpath("//spine/asset-clip")
        # Only the first word group [0.0-1.0] fits; the second [10.0-12.0] is past 75 frames (3s)
        assert len(clips) == 1
        assert clips[0].get("name") == "Keep 1"

    def test_export_handles_fps_rational_without_slash(self, tmp_path, sample_cutter_result):
        """FCPXML handles fps_rational without '/' (e.g. '25' or '29.97')."""
        media_info = MediaInfo(
            fps=25.0,
            fps_rational="25",
            duration=60.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4",
        )
        output_path = tmp_path / "output.fcpxml"
        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, media_info, output_path)

        tree = etree.parse(output_path)
        format_el = tree.xpath("//format")[0]
        assert format_el.get("frameDuration") == "1/25s"
        # Token-based approach: 4 word groups from sample_cutter_result
        assert len(tree.xpath("//spine/asset-clip")) == 4


class TestJSONExporter:
    """Tests for JSONExporter class."""

    def test_export_creates_valid_json(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that JSON export creates a valid JSON file."""
        output_path = tmp_path / "output.json"

        exporter = JSONExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        assert output_path.exists()

        # Parse JSON to validate
        with open(output_path) as f:
            data = json.load(f)

        assert "media_info" in data
        assert "cuts" in data
        assert "keep_segments" in data
        assert "words" in data
        assert "summary" in data

    def test_export_includes_media_info(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that JSON includes complete media info."""
        output_path = tmp_path / "output.json"

        exporter = JSONExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        with open(output_path) as f:
            data = json.load(f)

        media_info = data["media_info"]

        assert media_info["fps"] == 25.0
        assert media_info["fps_rational"] == "25/1"
        assert media_info["duration"] == 60.0
        assert media_info["width"] == 1920
        assert media_info["height"] == 1080
        assert media_info["has_video"] is True

    def test_export_includes_all_cuts(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that JSON includes all cuts with details."""
        output_path = tmp_path / "output.json"

        exporter = JSONExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        with open(output_path) as f:
            data = json.load(f)

        cuts = data["cuts"]

        assert len(cuts) == 3

        # Check first cut (sorted by start time)
        assert cuts[0]["start"] == 2.0
        assert cuts[0]["end"] == 3.2
        assert cuts[0]["duration"] == pytest.approx(1.2, rel=0.01)
        assert cuts[0]["type"] == "silence"

    def test_export_includes_words(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that JSON includes word classification."""
        output_path = tmp_path / "output.json"

        exporter = JSONExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        with open(output_path) as f:
            data = json.load(f)

        words = data["words"]

        # sample_cutter_result has 7 total words (6 kept + 1 filler)
        assert words["total"] == 7
        assert words["kept"] == 6
        assert words["cut"] == 1
        assert len(words["list"]) == 7

    def test_export_includes_keep_segments(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that JSON includes keep segments."""
        output_path = tmp_path / "output.json"

        exporter = JSONExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        with open(output_path) as f:
            data = json.load(f)

        keep_segments = data["keep_segments"]

        assert len(keep_segments) == 4
        assert keep_segments[0]["start"] == 0.0
        assert keep_segments[0]["end"] == 2.0

    def test_export_includes_summary(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that JSON includes summary statistics."""
        output_path = tmp_path / "output.json"

        exporter = JSONExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        with open(output_path) as f:
            data = json.load(f)

        summary = data["summary"]

        assert summary["original_duration"] == 60.0
        assert summary["final_duration"] == 57.5
        assert summary["cut_duration"] == 2.5
        assert summary["fillers_cut"] == 1
