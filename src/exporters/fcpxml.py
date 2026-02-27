"""FCPXML 1.9 exporter for DaVinci Resolve."""

import hashlib
from pathlib import Path

from lxml import etree

from src.exporters.base import BaseExporter
from src.models import CutterResult, MediaInfo


class FCPXMLExporter(BaseExporter):
    """Exporter for FCPXML 1.9 format compatible with DaVinci Resolve."""

    def export(
        self,
        result: CutterResult,
        media_info: MediaInfo,
        output_path: Path,
        whisperx_file: str = ""
    ) -> None:
        """
        Export segments to keep to FCPXML 1.9 format.

        Args:
            result: CutterResult with keep_segments
            media_info: Media file metadata
            output_path: Path to write the FCPXML file
            whisperx_file: Name of the WhisperX source file (unused)
        """
        keep_segments = self.sort_keep_segments_chronologically(result.keep_segments)

        # Parse frame rate rational (e.g., "47300/1671" for ~28.306 fps)
        fps_num, fps_den = media_info.fps_rational.split("/")
        fps_num = int(fps_num)
        fps_den = int(fps_den)

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

        # Asset element with proper time values
        file_url = Path(media_info.file_path).as_uri()
        etree.SubElement(
            resources,
            "asset",
            id="r2",
            name=Path(media_info.file_path).stem,
            uid=self._generate_uid(media_info.file_path),
            src=file_url,
            start="0s",
            duration=self._seconds_to_rational(media_info.duration, fps_num, fps_den),
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

        # Spine (timeline container) - created first to calculate total duration
        spine = etree.Element("spine")

        # Add keep segments as asset-clips
        # Calculate offsets in frames to avoid floating-point accumulation errors
        timeline_frame = 0
        for i, segment in enumerate(keep_segments, 1):
            # Convert segment times to frames
            start_frame = self._seconds_to_frames(segment.start, fps_num, fps_den)
            duration_frames = self._seconds_to_frames(segment.duration, fps_num, fps_den)

            etree.SubElement(
                spine,
                "asset-clip",
                name=f"Keep {i}",
                ref="r2",
                offset=self._frames_to_rational(timeline_frame, fps_num, fps_den),
                duration=self._frames_to_rational(duration_frames, fps_num, fps_den),
                start=self._frames_to_rational(start_frame, fps_num, fps_den),
                format="r1",
                tcFormat="NDF",
                audioRole="dialogue"
            )
            timeline_frame += duration_frames

        # Sequence - duration calculated from actual total frames
        sequence = etree.SubElement(
            project,
            "sequence",
            format="r1",
            duration=self._frames_to_rational(timeline_frame, fps_num, fps_den),
            tcStart="0s",
            tcFormat="NDF",
            audioLayout="stereo",
            audioRate="48k"
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
            raise RuntimeError(f"Failed to write FCPXML file: {e}")

    def _seconds_to_frames(self, seconds: float, fps_num: int, fps_den: int) -> int:
        """Convert seconds to number of frames (rounded)."""
        # frames = seconds * (fps_num / fps_den)
        # Use round() for proper rounding instead of truncation
        return round(seconds * fps_num / fps_den)

    def _frames_to_rational(self, frames: int, fps_num: int, fps_den: int) -> str:
        """Convert frame count to rational time (num/den)s format."""
        # Time in rational form: frames * frame_duration
        # = frames * (fps_den / fps_num) seconds
        # = (frames * fps_den) / fps_num seconds
        return f"{frames * fps_den}/{fps_num}s"

    def _seconds_to_rational(self, seconds: float, fps_num: int, fps_den: int) -> str:
        """Convert seconds to rational time (num/den)s format."""
        frames = self._seconds_to_frames(seconds, fps_num, fps_den)
        return self._frames_to_rational(frames, fps_num, fps_den)

    def _generate_uid(self, file_path: str) -> str:
        """Generate a UID based on file path."""
        return hashlib.md5(file_path.encode()).hexdigest().upper()
