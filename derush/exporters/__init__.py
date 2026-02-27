"""Export modules for different formats (FCPXML, EDL, JSON)."""

from derush.exporters.base import BaseExporter
from derush.exporters.json import JSONExporter

# Lazy imports for exporters that require optional dependencies
def get_fcpxml_exporter():
    """Get FCPXML exporter (requires lxml)."""
    from derush.exporters.fcpxml import FCPXMLExporter
    return FCPXMLExporter()


def get_edl_exporter():
    """Get EDL exporter."""
    from derush.exporters.edl import EDLExporter
    return EDLExporter()


__all__ = ["BaseExporter", "JSONExporter", "get_fcpxml_exporter", "get_edl_exporter"]
