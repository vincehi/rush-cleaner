"""Tests for exporter modules."""

import json
from pathlib import Path

import pytest
from lxml import etree

from src.exporters.base import BaseExporter
from src.exporters.fcpxml import FCPXMLExporter
from src.exporters.edl import EDLExporter
from src.exporters.json import JSONExporter
from src.models import MediaInfo


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

    def test_export_creates_valid_xml(self, tmp_path, sample_cuts, sample_media_info):
        """Test that FCPXML export creates a valid XML file."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

        assert output_path.exists()

        # Parse XML to validate structure
        tree = etree.parse(output_path)
        root = tree.getroot()

        assert root.tag == "fcpxml"
        assert root.get("version") == "1.9"

    def test_export_includes_resources(self, tmp_path, sample_cuts, sample_media_info):
        """Test that FCPXML includes resources section."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        resources = root.find("resources")
        assert resources is not None

        # Should have format and asset
        format_el = resources.find("format")
        asset_el = resources.find("asset")

        assert format_el is not None
        assert asset_el is not None

    def test_export_creates_keep_segments(self, tmp_path, sample_cuts, sample_media_info):
        """Test that FCPXML exports keep segments (segments between cuts)."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        # Find all asset-clips in spine (these are the keep segments)
        asset_clips = root.xpath("//asset-clip")

        # With cuts at [2.0-3.2], [5.0-6.0], [15.0-15.3] and duration 60s
        # Keep segments should be: [0-2], [3.2-5], [6-15], [15.3-60]
        assert len(asset_clips) == 4

        # Check that clips are named "Keep 1", "Keep 2", etc.
        assert asset_clips[0].get("name") == "Keep 1"
        assert asset_clips[1].get("name") == "Keep 2"
        assert asset_clips[2].get("name") == "Keep 3"
        assert asset_clips[3].get("name") == "Keep 4"

    def test_export_keep_segments_chronological(self, tmp_path, sample_cuts, sample_media_info):
        """Test that keep segments are in chronological order on timeline."""
        output_path = tmp_path / "output.fcpxml"

        exporter = FCPXMLExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        asset_clips = root.xpath("//asset-clip")

        # Check offsets are sequential (0s, then accumulating)
        # First clip should start at offset 0
        assert asset_clips[0].get("offset") == "0/60000s"

    def test_export_rational_fps(self, tmp_path, sample_cuts):
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
        exporter.export(sample_cuts, media_info, output_path)

        tree = etree.parse(output_path)
        root = tree.getroot()

        # Check format frameDuration
        format_el = root.xpath("//format")[0]
        frame_duration = format_el.get("frameDuration")

        # Should be in format "1001/30000s" (inverted from fps_rational)
        assert "1001/30000s" in frame_duration


class TestEDLExporter:
    """Tests for EDLExporter class."""

    def test_export_creates_valid_edl(self, tmp_path, sample_cuts, sample_media_info):
        """Test that EDL export creates a valid EDL file."""
        output_path = tmp_path / "output.edl"

        exporter = EDLExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

        assert output_path.exists()

        content = output_path.read_text()

        # Check header
        assert "TITLE:" in content
        assert "FCM:" in content

    def test_export_non_drop_frame(self, tmp_path, sample_cuts, sample_media_info):
        """Test EDL with non-drop-frame timecodes (25fps)."""
        output_path = tmp_path / "output.edl"

        exporter = EDLExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

        content = output_path.read_text()

        # Should have NON-DROP FRAME in header
        assert "NON-DROP FRAME" in content

        # Timecodes should use colons
        assert "00:00:02:" in content

    def test_export_drop_frame(self, tmp_path, sample_cuts, sample_media_info_2997):
        """Test EDL with drop-frame timecodes (29.97fps)."""
        output_path = tmp_path / "output.edl"

        exporter = EDLExporter()
        exporter.export(sample_cuts, sample_media_info_2997, output_path)

        content = output_path.read_text()

        # Should have DROP FRAME in header
        assert "DROP FRAME" in content

    def test_export_event_format(self, tmp_path, sample_cuts, sample_media_info):
        """Test EDL event format (CMX3600)."""
        output_path = tmp_path / "output.edl"

        exporter = EDLExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

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

    def test_export_includes_comments(self, tmp_path, sample_cuts, sample_media_info):
        """Test that EDL includes comment lines with labels."""
        output_path = tmp_path / "output.edl"

        exporter = EDLExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

        content = output_path.read_text()

        # Should have comment lines starting with *
        assert "* SILENCE" in content.upper()
        assert "* FILLER" in content.upper()


class TestJSONExporter:
    """Tests for JSONExporter class."""

    def test_export_creates_valid_json(self, tmp_path, sample_cuts, sample_media_info):
        """Test that JSON export creates a valid JSON file."""
        output_path = tmp_path / "output.json"

        exporter = JSONExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

        assert output_path.exists()

        # Parse JSON to validate
        with open(output_path) as f:
            data = json.load(f)

        assert "media_info" in data
        assert "cuts" in data
        assert "summary" in data

    def test_export_includes_media_info(self, tmp_path, sample_cuts, sample_media_info):
        """Test that JSON includes complete media info."""
        output_path = tmp_path / "output.json"

        exporter = JSONExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

        with open(output_path) as f:
            data = json.load(f)

        media_info = data["media_info"]

        assert media_info["fps"] == 25.0
        assert media_info["fps_rational"] == "25/1"
        assert media_info["duration"] == 60.0
        assert media_info["width"] == 1920
        assert media_info["height"] == 1080
        assert media_info["has_video"] is True

    def test_export_includes_all_cuts(self, tmp_path, sample_cuts, sample_media_info):
        """Test that JSON includes all cuts with details."""
        output_path = tmp_path / "output.json"

        exporter = JSONExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

        with open(output_path) as f:
            data = json.load(f)

        cuts = data["cuts"]

        assert len(cuts) == 3

        # Check first cut
        assert cuts[0]["start"] == 2.0
        assert cuts[0]["end"] == 3.2
        assert cuts[0]["duration"] == pytest.approx(1.2)
        assert cuts[0]["cut_type"] == "silence"

    def test_export_includes_summary(self, tmp_path, sample_cuts, sample_media_info):
        """Test that JSON includes summary statistics."""
        output_path = tmp_path / "output.json"

        exporter = JSONExporter()
        exporter.export(sample_cuts, sample_media_info, output_path)

        with open(output_path) as f:
            data = json.load(f)

        summary = data["summary"]

        assert summary["total_cuts"] == 3
        assert summary["silence_count"] == 2
        assert summary["filler_count"] == 1
        assert summary["total_cut_duration"] == pytest.approx(2.5, rel=0.1)
