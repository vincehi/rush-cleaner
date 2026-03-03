"""FCPXML 1.9 exporter for DaVinci Resolve."""

import logging
from pathlib import Path

from lxml import etree

from derush.exceptions import ExportError
from derush.exporters.base import BaseExporter
from derush.media_info import parse_fps_rational
from derush.models import CutterResult, MediaInfo

logger = logging.getLogger(__name__)

# Defaults for timeline naming and audio (overridable for different NLE / locales)
DEFAULT_EVENT_NAME = "Auto Derush"
DEFAULT_PROJECT_NAME = "Cuts"
DEFAULT_AUDIO_RATE = 48000


class FCPXMLExporter(BaseExporter):
    """Exporter for FCPXML 1.9 format compatible with DaVinci Resolve.

    V2 approach: Uses keep_segments directly without filler adjustment.
    Segments are already computed to exclude fillers.

    Stereo audio: use one asset per file with audioSources="2" and audioChannels="1"
    (two mono sources = L/R). One asset-clip per segment in the spine.
    """

    def export(
        self,
        result: CutterResult,
        media_info: MediaInfo,
        output_path: Path,
    ) -> None:
        """
        Export keep_segments to FCPXML 1.9 format.

        Args:
            result: CutterResult with keep_segments
            media_info: Media file metadata
            output_path: Path to write the FCPXML file
        """
        keep_segments = self.sort_keep_segments_chronologically(result.keep_segments)

        fps_num, fps_den = parse_fps_rational(media_info.fps_rational)

        # Create root element
        fcpxml = etree.Element("fcpxml", version="1.9")

        # Resources section
        resources = etree.SubElement(fcpxml, "resources")

        # Format element - use actual frame rate from media
        etree.SubElement(
            resources,
            "format",
            id="r1",
            name=f"FFVideoFormat{media_info.width}x{media_info.height}",
            frameDuration=f"{fps_den}/{fps_num}s",
            width=str(media_info.width),
            height=str(media_info.height),
        )

        # Single asset for the source file
        audio_sources = 2
        if media_info.audio_channels is not None and media_info.audio_channels > 0:
            audio_sources = media_info.audio_channels
        audio_rate = media_info.audio_sample_rate or DEFAULT_AUDIO_RATE
        file_url = Path(media_info.file_path).as_uri()
        total_asset_frames = (
            media_info.nb_frames
            if (media_info.nb_frames is not None and media_info.nb_frames > 0)
            else self._seconds_to_frames(media_info.duration, fps_num, fps_den)
        )
        duration_rat = self._frames_to_rational(total_asset_frames, fps_num, fps_den)
        asset = etree.SubElement(
            resources,
            "asset",
            id="r2",
            name=Path(media_info.file_path).name,
            format="r1",
            hasVideo="1" if media_info.has_video else "0",
            hasAudio="1",
            audioSources=str(audio_sources),
            audioChannels="1",
            audioRate=str(audio_rate),
            start="0s",
            duration=duration_rat,
        )
        etree.SubElement(asset, "media-rep", src=file_url, kind="original-media")

        # Library section (required for DaVinci Resolve)
        library = etree.SubElement(fcpxml, "library")
        event = etree.SubElement(library, "event", name=DEFAULT_EVENT_NAME)
        project = etree.SubElement(event, "project", name=DEFAULT_PROJECT_NAME)

        spine = etree.Element("spine")
        timeline_frame = 0

        for i, segment in enumerate(keep_segments, 1):
            # V2: Use segment boundaries directly (already exclude fillers)
            clip_start = segment.start
            clip_end = segment.end

            # Convert to frames
            start_frame = self._seconds_to_frames(clip_start, fps_num, fps_den, mode="round")
            end_frame = self._seconds_to_frames(clip_end, fps_num, fps_den, mode="round")
            duration_frames = end_frame - start_frame

            # Skip invalid clips
            if start_frame >= total_asset_frames:
                continue
            duration_frames = min(duration_frames, total_asset_frames - start_frame)
            if duration_frames <= 0:
                continue

            offset_rational = self._frames_to_rational(timeline_frame, fps_num, fps_den)
            duration_rational = self._frames_to_rational(duration_frames, fps_num, fps_den)
            start_rational = self._frames_to_rational(start_frame, fps_num, fps_den)

            clip_attrs = {
                "ref": "r2",
                "name": f"Keep {i}",
                "offset": offset_rational,
                "duration": duration_rational,
                "start": start_rational,
                "format": "r1",
                "tcFormat": "NDF",
                "audioRole": "dialogue",
                "enabled": "1",
            }
            asset_clip = etree.SubElement(spine, "asset-clip", **clip_attrs)
            etree.SubElement(
                asset_clip,
                "adjust-transform",
                scale="1 1",
                anchor="0 0",
                position="0 0",
            )

            timeline_frame += duration_frames

        if keep_segments and timeline_frame == 0:
            logger.warning(
                "FCPXML: no clips written (all segments past asset end or zero duration)"
            )

        # Sequence with stereo audio layout
        sequence = etree.SubElement(
            project,
            "sequence",
            format="r1",
            duration=self._frames_to_rational(timeline_frame, fps_num, fps_den),
            tcStart="0s",
            tcFormat="NDF",
            audioLayout="stereo",
            audioRate=str(audio_rate),
        )
        sequence.append(spine)

        # Write to file
        tree = etree.ElementTree(fcpxml)
        try:
            tree.write(
                output_path,
                pretty_print=True,
                xml_declaration=True,
                encoding="UTF-8",
                doctype="<!DOCTYPE fcpxml>",
            )
        except OSError as e:
            raise ExportError(f"Failed to write FCPXML file: {e}") from e

    def _seconds_to_frames(
        self, seconds: float, fps_num: int, fps_den: int, mode: str = "round"
    ) -> int:
        """Convert seconds to number of frames with mode selection."""
        import math

        raw = seconds * fps_num / fps_den
        if mode == "floor":
            return int(raw)
        elif mode == "ceil":
            return math.ceil(raw)
        return round(raw)

    def _frames_to_rational(self, frames: int, fps_num: int, fps_den: int) -> str:
        """Convert frame count to rational time (num/den)s format."""
        return f"{frames * fps_den}/{fps_num}s"
