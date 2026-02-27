"""Tests for exporter modules."""

import json
from pathlib import Path

import pytest
from lxml import etree

from derush.exporters.base import BaseExporter
from derush.exporters.fcpxml import FCPXMLExporter
from derush.exporters.edl import EDLExporter
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
        """Test that FCPXML exports keep segments."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        # Find all asset-clips in spine (these are the keep segments)
        asset_clips = root.xpath("//asset-clip")

        # With 4 keep segments in sample_cutter_result
        assert len(asset_clips) == 4

        # Check that clips are named "Keep 1", "Keep 2", etc.
        assert asset_clips[0].get("name") == "Keep 1"
        assert asset_clips[1].get("name") == "Keep 2"

    def test_export_keep_segments_chronological(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that keep segments are in chronological order on timeline."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        asset_clips = root.xpath("//asset-clip")

        # First clip should start at offset 0 (using fps_rational from media_info: "25/1")
        assert asset_clips[0].get("offset") == "0/25s"

    def test_export_no_timeline_discontinuities(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that there are no gaps between clips on timeline (no rounding errors)."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        asset_clips = root.xpath("//asset-clip")

        # Parse rational time values
        def parse_rational(time_str):
            # Format: "num/den s" or "num/dens"
            value = time_str.rstrip("s")
            num, den = map(int, value.split("/"))
            return num, den

        # Check that each clip's offset + duration equals next clip's offset
        for i in range(len(asset_clips) - 1):
            current = asset_clips[i]
            next_clip = asset_clips[i + 1]

            offset_num, offset_den = parse_rational(current.get("offset"))
            dur_num, dur_den = parse_rational(current.get("duration"))
            next_offset_num, next_offset_den = parse_rational(next_clip.get("offset"))

            # Calculate end position of current clip
            # offset + duration should equal next offset
            # Using common denominator
            end_num = offset_num * dur_den + dur_num * offset_den
            end_den = offset_den * dur_den

            # Cross-multiply to compare
            expected = end_num * next_offset_den
            actual = next_offset_num * end_den

            assert expected == actual, f"Discontinuity between clip {i+1} and {i+2}: {current.get('offset')} + {current.get('duration')} != {next_clip.get('offset')}"

    def test_export_rational_fps(self, tmp_path, sample_cutter_result):
        """Test that rational FPS is used correctly."""
        media_info = MediaInfo(
            fps=29.97,
            fps_rational="30000/1001",
            duration=60.0,
            width=1920,
            height=1080,
            has_video=True,
            file_path="/path/to/video.mp4"
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


class TestEDLExporter:
    """Tests for EDLExporter class."""

    def test_export_creates_valid_edl(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that EDL export creates a valid EDL file."""
        output_path = tmp_path / "output.edl"

        exporter = EDLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        assert output_path.exists()

        content = output_path.read_text()

        # Check header
        assert "TITLE:" in content
        assert "FCM:" in content

    def test_export_non_drop_frame(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test EDL with non-dropframe timecodes (25fps)."""
        output_path = tmp_path / "output.edl"

        exporter = EDLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        content = output_path.read_text()

        # Should have NON-DROP FRAME in header
        assert "NON-DROP FRAME" in content

        # Timecodes should use colons
        assert "00:00:02:" in content

    def test_export_drop_frame(self, tmp_path, sample_cutter_result, sample_media_info_2997):
        """Test EDL with drop-frame timecodes (29.97fps)."""
        output_path = tmp_path / "output.edl"

        exporter = EDLExporter()
        exporter.export(sample_cutter_result, sample_media_info_2997, output_path)

        content = output_path.read_text()

        # Should have DROP FRAME in header
        assert "DROP FRAME" in content

    def test_export_event_format(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test EDL event format (CMX3600)."""
        output_path = tmp_path / "output.edl"

        exporter = EDLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        content = output_path.read_text()
        lines = content.strip().split("\n")

        # Find event lines (start with 001, 002, etc.)
        event_lines = [l for l in lines if l.startswith("001") or l.startswith("002")]

        assert len(event_lines) >= 1

        # Event line should have format: NNN  AX      V     C        TC TC TC TC
        first_event = event_lines[0]
        assert "AX" in first_event
        assert "V" in first_event
        assert "C" in first_event

    def test_export_includes_comments(self, tmp_path, sample_cutter_result, sample_media_info):
        """Test that EDL includes comment lines with types."""
        output_path = tmp_path / "output.edl"

        exporter = EDLExporter()
        exporter.export(sample_cutter_result, sample_media_info, output_path)

        content = output_path.read_text()

        # Should have comment lines starting with *
        assert "* SILENCE" in content.upper()


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

        assert words["total"] == 3
        assert words["kept"] == 2
        assert words["cut"] == 1
        assert len(words["list"]) == 3

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
