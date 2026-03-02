"""Export modules for different formats (FCPXML, JSON)."""

from derush.exporters.base import BaseExporter
from derush.exporters.json import JSONExporter


def get_fcpxml_exporter():
    """Get FCPXML exporter (requires lxml)."""
    from derush.exporters.fcpxml import FCPXMLExporter

    return FCPXMLExporter()


__all__ = ["BaseExporter", "JSONExporter", "get_fcpxml_exporter"]
