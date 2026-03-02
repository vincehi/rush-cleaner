"""FCPXML 1.9 exporter for DaVinci Resolve."""

import logging
from pathlib import Path

from lxml import etree

from derush.exporters.base import BaseExporter
from derush.models import CutterResult, MediaInfo

logger = logging.getLogger(__name__)


class FCPXMLExporter(BaseExporter):
    """Exporter for FCPXML 1.9 format compatible with DaVinci Resolve.

    Stereo audio: use one asset per file with audioSources="2" and audioChannels="1"
    (two mono sources = L/R). One asset-clip per segment in the spine. See AGENTS.md
    section "Export FCPXML" for full rationale and Resolve workarounds.
    """

    def export(
        self,
        result: CutterResult,
        media_info: MediaInfo,
        output_path: Path,
    ) -> None:
        """
        Export segments to keep to FCPXML 1.9 format.

        Args:
            result: CutterResult with keep_segments
            media_info: Media file metadata
            output_path: Path to write the FCPXML file
        """
        keep_segments = self.sort_keep_segments_chronologically(result.keep_segments)

        # Parse frame rate rational (e.g., "47300/1671" or "25"); fallback for format without "/"
        if "/" in media_info.fps_rational:
            fps_num, fps_den = media_info.fps_rational.split("/", 1)
            fps_num, fps_den = int(fps_num), max(1, int(fps_den))
        else:
            fps_num = int(float(media_info.fps_rational))
            fps_den = 1

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
            height=str(media_info.height)
        )

        # Single asset for the source file — use media-rep child (DaVinci/Resolve style).
        # audioSources="2" + audioChannels="1" so Resolve sees two discrete channels (L/R) instead
        # of one stereo stream, which often imports as mono or one-sided in Resolve.
        # Use video stream nb_frames when available so asset duration never exceeds real frame count
        # (format duration can be longer than stream → "media offline" at end of timeline).
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
            audioSources="2",
            audioChannels="1",
            audioRate="48000",
            start="0s",
            duration=duration_rat,
        )
        etree.SubElement(asset, "media-rep", src=file_url, kind="original-media")

        # Library section (required for DaVinci Resolve)
        library = etree.SubElement(fcpxml, "library")
        event = etree.SubElement(library, "event", name="Dérushage Auto")
        project = etree.SubElement(event, "project", name="Cuts")

        # Spine: one asset-clip per segment (same ref r2) — avoids mono / one-sided audio.
        spine = etree.Element("spine")
        timeline_frame = 0
        for i, segment in enumerate(keep_segments, 1):
            start_frame = self._seconds_to_frames(segment.start, fps_num, fps_den)
            duration_frames = self._seconds_to_frames(segment.duration, fps_num, fps_den)
            # Clamp so no clip extends past asset end (avoids "media offline" for any segment)
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

        # Spine can be empty if all segments were past asset end (e.g. nb_frames too small)
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
            audioRate="48000"
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
                doctype="<!DOCTYPE fcpxml>"
            )
        except OSError as e:
            raise RuntimeError(f"Failed to write FCPXML file: {e}") from e

    def _seconds_to_frames(self, seconds: float, fps_num: int, fps_den: int) -> int:
        """Convert seconds to number of frames (rounded)."""
        return round(seconds * fps_num / fps_den)

    def _frames_to_rational(self, frames: int, fps_num: int, fps_den: int) -> str:
        """Convert frame count to rational time (num/den)s format."""
        return f"{frames * fps_den}/{fps_num}s"

    def _seconds_to_rational(
        self, seconds: float, fps_num: int, fps_den: int
    ) -> str:
        """Convert seconds to rational time (num/den)s format."""
        frames = self._seconds_to_frames(seconds, fps_num, fps_den)
        return self._frames_to_rational(frames, fps_num, fps_den)
