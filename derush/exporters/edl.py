"""EDL (CMX3600) exporter for DaVinci Resolve, Premiere Pro, and Avid."""

from pathlib import Path

from derush.exporters.base import BaseExporter
from derush.models import CutterResult, MediaInfo, NTSC_FPS, NTSC_FPS_TOLERANCE


class EDLExporter(BaseExporter):
    """Exporter for EDL CMX3600 format."""

    def export(
        self,
        result: CutterResult,
        media_info: MediaInfo,
        output_path: Path,
    ) -> None:
        """
        Export cuts to EDL CMX3600 format.

        Args:
            result: CutterResult with cuts
            media_info: Media file metadata
            output_path: Path to write the EDL file
        """
        cuts = self.sort_cuts_chronologically(result.cuts)

        # Determine drop-frame mode
        is_drop_frame = abs(media_info.fps - NTSC_FPS) < NTSC_FPS_TOLERANCE
        fcm_mode = "DROP FRAME" if is_drop_frame else "NON-DROP FRAME"

        lines = []

        # Header
        source_name = Path(media_info.file_path).stem
        lines.append(f"TITLE: Dérushage Auto - {source_name}")
        lines.append(f"FCM: {fcm_mode}")
        lines.append("")

        # Event entries
        for i, cut in enumerate(cuts, 1):
            event_num = f"{i:03d}"
            reel = "AX"

            # Timecodes
            tc_in = self._seconds_to_timecode(cut.start, media_info.fps, is_drop_frame)
            tc_out = self._seconds_to_timecode(cut.end, media_info.fps, is_drop_frame)

            # EDL line format
            line = f"{event_num}  {reel:6s}  V     C        {tc_in} {tc_out} {tc_in} {tc_out}"
            lines.append(line)

            # Comment line with type and reason
            label = f"{cut.cut_type.value.upper()}"
            if cut.word:
                label += f" ({cut.word})"
            elif cut.reason.value:
                label += f" ({cut.reason.value})"
            comment = f"* {label}"
            lines.append(comment)
            lines.append("")

        # Write to file
        try:
            output_path.write_text("\n".join(lines))
        except OSError as e:
            raise RuntimeError(f"Failed to write EDL file: {e}")

    def _seconds_to_timecode(
        self,
        seconds: float,
        fps: float,
        is_drop_frame: bool
    ) -> str:
        """
        Convert seconds to timecode string (HH:MM:SS:FF or HH:MM:SS;FF).

        Args:
            seconds: Time in seconds
            fps: Frames per second
            is_drop_frame: Whether to use drop-frame notation

        Returns:
            Timecode string (e.g., "00:01:02:15" or "00:01:02;15")
        """
        total_frames = int(seconds * fps)

        # For 29.97 drop-frame
        if is_drop_frame:
            return self._frames_to_drop_frame_timecode(total_frames)

        # Standard non-drop-frame calculation
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frames = int((seconds % 1) * fps)

        separator = ";" if is_drop_frame else ":"
        return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{frames:02d}"

    def _frames_to_drop_frame_timecode(self, total_frames: int) -> str:
        """
        Convert frame count to drop-frame timecode for 29.97fps.

        Drop-frame skips frames 0 and 1 at the start of each minute,
        except for every 10th minute.
        """
        fps = 30  # Drop-frame uses 30 as base
        frames_per_minute = fps * 60
        frames_per_10_minutes = frames_per_minute * 10

        # Calculate 10-minute blocks
        ten_minute_blocks = total_frames // frames_per_10_minutes
        remaining_frames = total_frames % frames_per_10_minutes

        # Calculate minutes within 10-minute block (with drop-frame adjustment)
        minutes_in_block = remaining_frames // frames_per_minute
        drop_frames = minutes_in_block - (minutes_in_block // 10)

        # Adjust remaining frames
        remaining_frames -= drop_frames * 2

        # Calculate hours, minutes, seconds, frames
        hours = ten_minute_blocks * 10 + remaining_frames // (fps * 3600)
        remaining_frames %= fps * 3600
        minutes = remaining_frames // (fps * 60)
        remaining_frames %= fps * 60
        seconds = remaining_frames // fps
        frames = remaining_frames % fps

        return f"{hours:02d}:{minutes:02d}:{seconds:02d};{frames:02d}"
