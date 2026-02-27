"""Base exporter class for all export formats."""

from abc import ABC, abstractmethod
from pathlib import Path

from src.models import Cut, MediaInfo


class BaseExporter(ABC):
    """Abstract base class for exporters."""

    @abstractmethod
    def export(
        self,
        cuts: list[Cut],
        media_info: MediaInfo,
        output_path: Path
    ) -> None:
        """
        Export cuts to the specified format.

        Args:
            cuts: List of cuts to export
            media_info: Media file metadata
            output_path: Path to write the output file
        """
        pass

    @staticmethod
    def sort_cuts_chronologically(cuts: list[Cut]) -> list[Cut]:
        """Sort cuts by start time."""
        return sorted(cuts, key=lambda c: c.start)
