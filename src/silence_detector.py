"""Silence detection based on gaps between transcribed segments."""

from src.models import Cut, Segment


def detect_silences(
    segments: list[Segment],
    min_duration: float = 0.5,
    total_duration: float = 0.0
) -> list[Cut]:
    """
    Detect silent gaps between transcribed segments.

    Args:
        segments: List of transcribed segments (must be sorted by start time)
        min_duration: Minimum silence duration in seconds (default: 0.5s)
        total_duration: Total duration of the media file (for detecting silence at end)

    Returns:
        List of Cut objects representing silent sections
    """
    if not segments:
        # Entire file is silent
        if total_duration > 0:
            return [Cut(
                start=0.0,
                end=total_duration,
                cut_type="silence",
                label=f"Silence {total_duration:.1f}s"
            )]
        return []

    cuts = []

    # Check for silence at the beginning
    if segments[0].start >= min_duration:
        duration = segments[0].start
        cuts.append(Cut(
            start=0.0,
            end=segments[0].start,
            cut_type="silence",
            label=f"Silence {duration:.1f}s"
        ))

    # Check for gaps between segments
    for i in range(len(segments) - 1):
        gap_start = segments[i].end
        gap_end = segments[i + 1].start
        gap_duration = gap_end - gap_start

        if gap_duration >= min_duration:
            cuts.append(Cut(
                start=gap_start,
                end=gap_end,
                cut_type="silence",
                label=f"Silence {gap_duration:.1f}s"
            ))

    # Check for silence at the end
    if total_duration > 0:
        last_end = segments[-1].end
        end_silence = total_duration - last_end

        if end_silence >= min_duration:
            cuts.append(Cut(
                start=last_end,
                end=total_duration,
                cut_type="silence",
                label=f"Silence {end_silence:.1f}s"
            ))

    return cuts
