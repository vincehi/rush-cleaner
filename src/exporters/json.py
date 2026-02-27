"""JSON exporter for debugging and custom integrations."""

import json
from pathlib import Path

from src.exporters.base import BaseExporter
from src.models import Cut, MediaInfo


class JSONExporter(BaseExporter):
    """Exporter for JSON format (debug and custom integrations)."""

    def export(
        self,
        cuts: list[Cut],
        media_info: MediaInfo,
        output_path: Path
    ) -> None:
        """
        Export cuts to JSON format.

        Args:
            cuts: List of cuts to export
            media_info: Media file metadata
            output_path: Path to write the JSON file
        """
        cuts = self.sort_cuts_chronologically(cuts)

        data = {
            "media_info": {
                "fps": media_info.fps,
                "fps_rational": media_info.fps_rational,
                "duration": media_info.duration,
                "width": media_info.width,
                "height": media_info.height,
                "has_video": media_info.has_video,
                "file_path": media_info.file_path,
            },
            "cuts": [
                {
                    "start": cut.start,
                    "end": cut.end,
                    "duration": cut.end - cut.start,
                    "cut_type": cut.cut_type,
                    "label": cut.label,
                }
                for cut in cuts
            ],
            "summary": {
                "total_cuts": len(cuts),
                "silence_count": sum(1 for c in cuts if c.cut_type == "silence"),
                "filler_count": sum(1 for c in cuts if c.cut_type == "filler"),
                "total_cut_duration": sum(c.end - c.start for c in cuts),
            }
        }

        try:
            output_path.write_text(json.dumps(data, indent=2))
        except OSError as e:
            raise RuntimeError(f"Failed to write JSON file: {e}")
