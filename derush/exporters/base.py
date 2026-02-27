"""Base exporter class for all export formats."""

from abc import ABC, abstractmethod
from pathlib import Path

from derush.models import CutterResult, MediaInfo


class BaseExporter(ABC):
    """Abstract base class for exporters."""

    @abstractmethod
    def export(
        self,
        result: CutterResult,
        media_info: MediaInfo,
        output_path: Path,
    ) -> None:
        """
        Export cutting result to the specified format.

        Args:
            result: CutterResult with words, cuts, keep_segments, and summary
            media_info: Media file metadata
            output_path: Path to write the output file
        """
        pass

    @staticmethod
    def sort_cuts_chronologically(cuts: list["Cut"]) -> list["Cut"]:
        """Sort cuts by start time."""
        return sorted(cuts, key=lambda c: c.start)

    @staticmethod
    def sort_keep_segments_chronologically(segments: list["KeepSegment"]) -> list["KeepSegment"]:
        """Sort keep segments by start time."""
        return sorted(segments, key=lambda s: s.start)
