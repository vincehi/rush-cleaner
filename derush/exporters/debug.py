"""Debug exporter for intermediate pipeline stages.

Generates JSON files at each step of the V2 pipeline for debugging:
1. *_1_loaded.json - Raw words from WhisperX
2. *_2_corrected.json - Words after timing correction
3. *_3_classified.json - Words with filler/kept status
4. *_4_filtered.json - Only kept tokens
5. *_5_timeline.json - TimelineTokens with continuous positions
6. *_6_segments.json - Merged TimelineSegments
"""

import json
from dataclasses import asdict
from pathlib import Path

from derush.models import TimelineSegment, TimelineToken, Word


def export_words_json(words: list[Word], output_path: Path) -> None:
    """Export list of Word objects to JSON."""
    data = []
    for w in words:
        data.append({
            "word": w.word,
            "start": round(w.start, 3),
            "end": round(w.end, 3),
            "duration": round(w.end - w.start, 3),
            "score": round(w.score, 3) if w.score else None,
            "status": w.status.value if hasattr(w, "status") else None,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_timeline_tokens_json(tokens: list[TimelineToken], output_path: Path) -> None:
    """Export list of TimelineToken objects to JSON."""
    data = []
    for t in tokens:
        data.append({
            "text": t.text,
            "original_start": round(t.original_start, 3),
            "original_end": round(t.original_end, 3),
            "original_duration": round(t.duration, 3),
            "timeline_start": round(t.timeline_start, 3),
            "timeline_end": round(t.timeline_end, 3),
            "timeline_duration": round(t.timeline_end - t.timeline_start, 3),
            "corrected": t.corrected,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_timeline_segments_json(segments: list[TimelineSegment], output_path: Path) -> None:
    """Export list of TimelineSegment objects to JSON."""
    data = []
    for i, s in enumerate(segments, 1):
        data.append({
            "segment_id": i,
            "original_start": round(s.original_start, 3),
            "original_end": round(s.original_end, 3),
            "original_duration": round(s.duration, 3),
            "timeline_start": round(s.timeline_start, 3),
            "timeline_end": round(s.timeline_end, 3),
            "timeline_duration": round(s.timeline_end - s.timeline_start, 3),
            "text_preview": s.text,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class DebugExporter:
    """Export debug files for each pipeline stage."""

    def __init__(self, base_path: Path):
        """Initialize with base output path (without extension).

        Args:
            base_path: Base path for debug files (e.g., /path/to/output_video)
        """
        self.base_path = base_path

    def export_loaded(self, words: list[Word]) -> Path:
        """Export stage 1: Raw loaded words."""
        path = self.base_path.with_suffix(".1_loaded.json")
        export_words_json(words, path)
        return path

    def export_corrected(self, words: list[Word]) -> Path:
        """Export stage 2: Corrected words."""
        path = self.base_path.with_suffix(".2_corrected.json")
        export_words_json(words, path)
        return path

    def export_classified(self, words: list[Word]) -> Path:
        """Export stage 3: Classified words (filler/kept)."""
        path = self.base_path.with_suffix(".3_classified.json")
        export_words_json(words, path)
        return path

    def export_filtered(self, words: list[Word]) -> Path:
        """Export stage 4: Filtered words (only kept)."""
        path = self.base_path.with_suffix(".4_filtered.json")
        export_words_json(words, path)
        return path

    def export_timeline(self, tokens: list[TimelineToken]) -> Path:
        """Export stage 5: Timeline tokens."""
        path = self.base_path.with_suffix(".5_timeline.json")
        export_timeline_tokens_json(tokens, path)
        return path

    def export_segments(self, segments: list[TimelineSegment]) -> Path:
        """Export stage 6: Merged segments."""
        path = self.base_path.with_suffix(".6_segments.json")
        export_timeline_segments_json(segments, path)
        return path

    def cleanup(self) -> None:
        """Remove all debug files."""
        for suffix in [
            ".1_loaded.json",
            ".2_corrected.json",
            ".3_classified.json",
            ".4_filtered.json",
            ".5_timeline.json",
            ".6_segments.json",
        ]:
            path = self.base_path.with_suffix(suffix)
            if path.exists():
                path.unlink()
