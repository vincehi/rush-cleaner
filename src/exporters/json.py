"""JSON exporter for debugging and custom integrations."""

import json
from pathlib import Path

from src.exporters.base import BaseExporter
from src.models import CutterResult, MediaInfo


class JSONExporter(BaseExporter):
    """Exporter for enriched JSON format with debug info."""

    def export(
        self,
        result: CutterResult,
        media_info: MediaInfo,
        output_path: Path,
    ) -> None:
        """
        Export cutting result to enriched JSON format.

        Args:
            result: CutterResult with words, cuts, keep_segments, and summary
            media_info: Media file metadata
            output_path: Path to write the JSON file
        """
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
            "words": {
                "total": result.total_words,
                "kept": result.kept_words,
                "cut": result.filler_words,
                "list": [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "score": w.score,
                        "status": w.status.value
                    }
                    for w in result.words
                ]
            },
            "cuts": [
                {
                    "start": c.start,
                    "end": c.end,
                    "duration": round(c.end - c.start, 3),
                    "type": c.cut_type.value,
                    "reason": c.reason.value,
                    **({"word": c.word} if c.word else {})
                }
                for c in self.sort_cuts_chronologically(result.cuts)
            ],
            "keep_segments": [
                {
                    "start": s.start,
                    "end": s.end,
                    "duration": round(s.duration, 3)
                }
                for s in self.sort_keep_segments_chronologically(result.keep_segments)
            ],
            "summary": {
                "original_duration": round(result.original_duration, 3),
                "final_duration": round(result.final_duration, 3),
                "cut_duration": round(result.cut_duration, 3),
                "cut_percentage": round(result.cut_percentage, 1),
                "fillers_cut": result.filler_words,
                "silences_cut": sum(1 for c in result.cuts if c.cut_type.value == "silence"),
                "gaps_cut": sum(1 for c in result.cuts if c.cut_type.value == "gap"),
            }
        }

        try:
            output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except OSError as e:
            raise RuntimeError(f"Failed to write JSON file: {e}")
