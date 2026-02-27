"""Export modules for different formats (FCPXML, EDL, JSON)."""

from src.exporters.base import BaseExporter
from src.exporters.json import JSONExporter

# Lazy imports for exporters that require optional dependencies
def get_fcpxml_exporter():
    """Get FCPXML exporter (requires lxml)."""
    from src.exporters.fcpxml import FCPXMLExporter
    return FCPXMLExporter()


def get_edl_exporter():
    """Get EDL exporter."""
    from src.exporters.edl import EDLExporter
    return EDLExporter()


__all__ = ["BaseExporter", "JSONExporter", "get_fcpxml_exporter", "get_edl_exporter"]
