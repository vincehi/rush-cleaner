"""Smoke tests to verify module imports work correctly."""

import pytest


class TestModuleImports:
    """Tests to verify all modules can be imported without errors."""

    def test_import_models(self):
        """Test importing models module."""
        from src.models import MediaInfo, Segment, Word, Cut
        assert MediaInfo is not None
        assert Segment is not None
        assert Word is not None
        assert Cut is not None

    def test_import_media_info(self):
        """Test importing media_info module."""
        from src.media_info import get_media_info
        assert get_media_info is not None

    def test_import_transcriber(self):
        """Test importing transcriber module."""
        from src.transcriber import transcribe
        assert transcribe is not None

    def test_import_silence_detector(self):
        """Test importing silence_detector module."""
        from src.silence_detector import detect_silences
        assert detect_silences is not None

    def test_import_filler_detector(self):
        """Test importing filler_detector module."""
        from src.filler_detector import detect_fillers
        assert detect_fillers is not None

    def test_import_exporters(self):
        """Test importing exporter modules."""
        from src.exporters.base import BaseExporter
        from src.exporters.fcpxml import FCPXMLExporter
        from src.exporters.edl import EDLExporter
        from src.exporters.json_export import JSONExporter

        assert BaseExporter is not None
        assert FCPXMLExporter is not None
        assert EDLExporter is not None
        assert JSONExporter is not None

    def test_import_cli(self):
        """Test importing CLI module."""
        from src.cli import app
        assert app is not None
