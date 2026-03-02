"""Smoke tests to verify module imports work correctly."""

import pytest


class TestModuleImports:
    """Tests to verify all modules can be imported without errors."""

    def test_import_models(self):
        """Test importing models module."""
        from derush.models import MediaInfo, Segment, Word, Cut
        assert MediaInfo is not None
        assert Segment is not None
        assert Word is not None
        assert Cut is not None

    def test_import_media_info(self):
        """Test importing media_info module."""
        from derush.media_info import get_media_info
        assert get_media_info is not None

    def test_import_transcriber(self):
        """Test importing transcriber module."""
        from derush.transcriber import transcribe
        assert transcribe is not None

    def test_import_cutter(self):
        """Test importing cutter module."""
        from derush.cutter import run_pipeline, classify_words, compute_cuts
        assert run_pipeline is not None
        assert classify_words is not None
        assert compute_cuts is not None

    def test_import_exporters(self):
        """Test importing exporter modules."""
        from derush.exporters.base import BaseExporter
        from derush.exporters.fcpxml import FCPXMLExporter
        from derush.exporters.json import JSONExporter

        assert BaseExporter is not None
        assert FCPXMLExporter is not None
        assert JSONExporter is not None

    def test_import_cli(self):
        """Test importing CLI module."""
        from derush.cli import app
        assert app is not None
