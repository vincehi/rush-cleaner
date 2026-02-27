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

    def test_import_cutter(self):
        """Test importing cutter module."""
        from src.cutter import run_pipeline, classify_words, compute_cuts
        assert run_pipeline is not None
        assert classify_words is not None
        assert compute_cuts is not None

    def test_import_exporters(self):
        """Test importing exporter modules."""
        from src.exporters.base import BaseExporter
        from src.exporters.fcpxml import FCPXMLExporter
        from src.exporters.edl import EDLExporter
        from src.exporters.json import JSONExporter

        assert BaseExporter is not None
        assert FCPXMLExporter is not None
        assert EDLExporter is not None
        assert JSONExporter is not None

    def test_import_cli(self):
        """Test importing CLI module."""
        from src.cli import app
        assert app is not None
