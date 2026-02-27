"""FCPXML 1.9 exporter for DaVinci Resolve."""

import hashlib
from pathlib import Path
from urllib.request import pathname2url

from lxml import etree

from src.exporters.base import BaseExporter
from src.models import Cut, MediaInfo


class FCPXMLExporter(BaseExporter):
    """Exporter for FCPXML 1.9 format compatible with DaVinci Resolve."""

    def export(
        self,
        cuts: list[Cut],
        media_info: MediaInfo,
        output_path: Path
    ) -> None:
        """
        Export segments to keep to FCPXML 1.9 format.

        Args:
            cuts: List of cuts (segments to remove)
            media_info: Media file metadata
            output_path: Path to write the FCPXML file
        """
        cuts = self.sort_cuts_chronologically(cuts)

        # Calculate segments to keep (between cuts)
        keep_segments = self._calculate_keep_segments(cuts, media_info.duration)

        # Parse frame rate rational
        fps_num, fps_den = media_info.fps_rational.split("/")
        fps = float(fps_num) / float(fps_den)

        # Create root element
        fcpxml = etree.Element("fcpxml", version="1.9")

        # Resources section
        resources = etree.SubElement(fcpxml, "resources")

        # Format element
        etree.SubElement(
            resources,
            "format",
            id="r1",
            name=f"FFVideoFormat{media_info.width}x{media_info.height}",
            frameDuration=f"{fps_den}/{fps_num}s",
            width=str(media_info.width),
            height=str(media_info.height)
        )

        # Asset element with proper time values
        file_url = "file://" + pathname2url(media_info.file_path)
        asset = etree.SubElement(
            resources,
            "asset",
            id="r2",
            name=Path(media_info.file_path).stem,
            uid=self._generate_uid(media_info.file_path),
            src=file_url,
            start="0s",
            duration=self._seconds_to_rational(media_info.duration, fps),
            hasVideo="1" if media_info.has_video else "0",
            hasAudio="1",
            audioSources="1",
            audioChannels="2",
            audioRate="48k",
            format="r1"
        )

        # Library section (required for DaVinci Resolve)
        library = etree.SubElement(fcpxml, "library")
        event = etree.SubElement(library, "event", name="Dérushage Auto")
        project = etree.SubElement(event, "project", name="Cuts")

        # Sequence
        total_duration = sum(seg["duration"] for seg in keep_segments)
        sequence = etree.SubElement(
            project,
            "sequence",
            format="r1",
            duration=self._seconds_to_rational(total_duration, fps),
            tcStart="0s",
            tcFormat="NDF",
            audioLayout="stereo",
            audioRate="48k"
        )

        # Spine (timeline container)
        spine = etree.SubElement(sequence, "spine")

        # Add keep segments as asset-clips
        timeline_offset = 0.0
        for i, segment in enumerate(keep_segments, 1):
            asset_clip = etree.SubElement(
                spine,
                "asset-clip",
                name=f"Keep {i}",
                ref="r2",
                offset=self._seconds_to_rational(timeline_offset, fps),
                duration=self._seconds_to_rational(segment["duration"], fps),
                start=self._seconds_to_rational(segment["source_start"], fps),
                format="r1",
                tcFormat="NDF",
                audioRole="dialogue"
            )
            timeline_offset += segment["duration"]

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
            raise RuntimeError(f"Failed to write FCPXML file: {e}")

    def _calculate_keep_segments(
        self,
        cuts: list[Cut],
        total_duration: float
    ) -> list[dict]:
        """
        Calculate segments to keep between cuts.

        Args:
            cuts: Sorted list of cuts (segments to remove)
            total_duration: Total media duration

        Returns:
            List of segments to keep with source_start, duration
        """
        segments = []
        prev_end = 0.0

        for cut in cuts:
            if cut.start > prev_end:
                segments.append({
                    "source_start": prev_end,
                    "duration": cut.start - prev_end
                })
            prev_end = cut.end

        # Add final segment if there's content after the last cut
        if prev_end < total_duration:
            segments.append({
                "source_start": prev_end,
                "duration": total_duration - prev_end
            })

        return segments

    def _seconds_to_rational(self, seconds: float, fps: float) -> str:
        """Convert seconds to rational time (num/den)s format."""
        # Use a high precision denominator for accuracy
        denominator = 60000  # Common base for most frame rates
        numerator = int(seconds * denominator)
        return f"{numerator}/{denominator}s"

    def _generate_uid(self, file_path: str) -> str:
        """Generate a UID based on file path."""
        return hashlib.md5(file_path.encode()).hexdigest().upper()
