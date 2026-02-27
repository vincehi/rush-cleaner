"""Filler word detection in transcribed segments.

This module implements a "keep segments" approach (positive selection):
- Source of truth: aligned words with timestamps
- A word is either "to keep" (content) or "to cut" (filler)
- We build keep ranges from words to keep, then derive cuts from those
"""

import re
from dataclasses import dataclass
from typing import Optional

from src.models import Cut, Segment, Word


# Default filler words by language
DEFAULT_FILLERS = {
    "fr": ["euh", "ben", "du coup", "en fait", "bon", "bah", "quoi", "hmm", "tu vois"],
    "en": ["um", "uh", "like", "you know", "i mean", "basically", "so", "right"],
}

# Phonetic variants for common fillers (Whisper often transcribes prolonged sounds with extra letters)
FILLER_VARIANTS = {
    "um": ["mm", "hm", "hmm", "umm", "ummm", "ummmm"],
    "uh": ["ah", "uhh", "uhhh"],
    "euh": ["eu", "euu", "euhh", "euhhh"],
    "hmm": ["mm", "hm", "hmm", "mhm", "hmmm", "hmmmm", "hmmmmm"],
    "quoi": ["ko", "kw"],
}


@dataclass
class TimeRange:
    """Represents a time range with start and end."""
    start: float
    end: float


def _normalize_word(word: str) -> str:
    """Normalize word for matching (lowercase, strip punctuation)."""
    return re.sub(r"[^\w\s]", "", word.lower()).strip()


def _build_filler_patterns(fillers: list[str]) -> dict[str, re.Pattern]:
    """Build regex patterns for filler matching with word boundaries."""
    patterns = {}

    for filler in fillers:
        # Check if this filler has known variants
        variants = [filler]
        for base, vars_list in FILLER_VARIANTS.items():
            if filler == base:
                variants.extend(vars_list)
            elif filler in vars_list:
                variants.append(base)
                variants.extend(vars_list)

        # Create pattern that matches any variant
        escaped_variants = [re.escape(v) for v in set(variants)]
        pattern_str = r"^(?:" + "|".join(escaped_variants) + r")$"
        patterns[filler] = re.compile(pattern_str, re.IGNORECASE)

    return patterns


def is_filler(word: str, filler_patterns: dict[str, re.Pattern]) -> bool:
    """
    Check if a word is a filler.

    Args:
        word: The word to check
        filler_patterns: Dictionary of compiled regex patterns for fillers

    Returns:
        True if the word matches any filler pattern
    """
    normalized = _normalize_word(word)
    if not normalized:
        return False

    for pattern in filler_patterns.values():
        if pattern.match(normalized):
            return True
    return False


def _merge_ranges(ranges: list[TimeRange], tolerance: float = 0.05) -> list[TimeRange]:
    """
    Merge overlapping or adjacent time ranges.

    Args:
        ranges: List of time ranges (potentially unsorted and overlapping)
        tolerance: Maximum gap to consider as adjacent (default: 0.05s)

    Returns:
        List of merged ranges, sorted by start time
    """
    if not ranges:
        return []

    # Sort by start time
    sorted_ranges = sorted(ranges, key=lambda r: r.start)

    merged = [sorted_ranges[0]]

    for current in sorted_ranges[1:]:
        previous = merged[-1]

        # Check if current range overlaps or is adjacent to the previous one
        if current.start <= previous.end + tolerance:
            # Extend the previous range
            merged[-1] = TimeRange(
                start=previous.start,
                end=max(previous.end, current.end)
            )
        else:
            merged.append(current)

    return merged


def _subtract_ranges(
    keep_ranges: list[TimeRange],
    silence_ranges: list[TimeRange],
    tolerance: float = 0.05
) -> list[TimeRange]:
    """
    Subtract silence ranges from keep ranges.

    Args:
        keep_ranges: Ranges to keep (speech content)
        silence_ranges: Ranges to remove (silences)
        tolerance: Tolerance for range boundaries

    Returns:
        Keep ranges with silences removed
    """
    if not silence_ranges:
        return keep_ranges

    if not keep_ranges:
        return []

    result = []

    for keep in keep_ranges:
        current_start = keep.start
        current_end = keep.end

        for silence in silence_ranges:
            # If silence is completely outside this keep range, skip
            if silence.end <= current_start or silence.start >= current_end:
                continue

            # If silence starts after current_start, we have a piece before the silence
            if silence.start > current_start + tolerance:
                result.append(TimeRange(start=current_start, end=silence.start))

            # Move current_start past the silence
            current_start = max(current_start, silence.end)

        # If there's still range left after all silences, add it
        if current_start < current_end - tolerance:
            result.append(TimeRange(start=current_start, end=current_end))

    return result


def _ranges_to_cuts(keep_ranges: list[TimeRange], total_duration: float) -> list[Cut]:
    """
    Convert keep ranges to cuts (complement of keep ranges).

    Args:
        keep_ranges: Ranges to keep (sorted, non-overlapping)
        total_duration: Total duration of the media

    Returns:
        List of Cut objects representing what to remove
    """
    if not keep_ranges:
        # Everything is a cut
        if total_duration > 0:
            return [Cut(
                start=0.0,
                end=total_duration,
                cut_type="mixed",
                label="No content to keep"
            )]
        return []

    cuts = []

    # Check for gap at the beginning
    if keep_ranges[0].start > 0:
        duration = keep_ranges[0].start
        cuts.append(Cut(
            start=0.0,
            end=keep_ranges[0].start,
            cut_type="silence",
            label=f"Silence {duration:.1f}s"
        ))

    # Gaps between keep ranges
    for i in range(len(keep_ranges) - 1):
        gap_start = keep_ranges[i].end
        gap_end = keep_ranges[i + 1].start
        gap_duration = gap_end - gap_start

        if gap_duration > 0.01:  # Only add if there's an actual gap
            cuts.append(Cut(
                start=gap_start,
                end=gap_end,
                cut_type="mixed",
                label=f"Cut {gap_duration:.1f}s"
            ))

    # Check for gap at the end
    if keep_ranges[-1].end < total_duration:
        duration = total_duration - keep_ranges[-1].end
        cuts.append(Cut(
            start=keep_ranges[-1].end,
            end=total_duration,
            cut_type="silence",
            label=f"Silence {duration:.1f}s"
        ))

    return cuts


def get_keep_segments(
    segments: list[Segment],
    language: str = "fr",
    custom_fillers: Optional[list[str]] = None,
    min_silence: float = 0.5,
    total_duration: float = 0.0
) -> list[Cut]:
    """
    Generate cuts based on "words to keep" approach (positive selection).

    This function:
    1. Identifies words to keep (non-filler words)
    2. Builds time ranges from those words
    3. Merges adjacent/overlapping ranges
    4. Adds speech continuity ranges (gaps between segments < min_silence)
    5. Subtracts silences (gaps between segments >= min_silence)
    6. Returns cuts = complement of keep ranges

    Args:
        segments: List of transcribed segments
        language: Language code ("fr" or "en")
        custom_fillers: Optional list of custom filler words to detect
        min_silence: Minimum silence duration to cut (default: 0.5s)
        total_duration: Total duration of the media file

    Returns:
        List of Cut objects representing what to remove
    """
    # Build filler patterns
    fillers = DEFAULT_FILLERS.get(language, DEFAULT_FILLERS["en"])
    if custom_fillers:
        fillers = list(set(fillers + [f.lower().strip() for f in custom_fillers]))
    filler_patterns = _build_filler_patterns(fillers)

    # Step 1: Collect keep ranges from words
    keep_ranges: list[TimeRange] = []

    for segment in segments:
        # Word-level: add ranges for non-filler words
        for word in segment.words:
            if not is_filler(word.word, filler_patterns):
                keep_ranges.append(TimeRange(start=word.start, end=word.end))

        # Segment-level fallback: if segment has no words and is not a filler, keep it
        # This handles cases where WhisperX doesn't return word-level alignment
        if not segment.words:
            normalized_text = _normalize_word(segment.text)
            if normalized_text and not is_filler(segment.text, filler_patterns):
                keep_ranges.append(TimeRange(start=segment.start, end=segment.end))

    # Step 2: Merge adjacent/overlapping ranges with tolerance
    keep_ranges = _merge_ranges(keep_ranges, tolerance=0.05)

    # Step 3: Add speech continuity ranges (gaps between segments < min_silence)
    # These gaps should be kept to preserve natural speech flow
    if segments:
        continuity_ranges: list[TimeRange] = []
        for i in range(len(segments) - 1):
            gap_start = segments[i].end
            gap_end = segments[i + 1].start
            gap_duration = gap_end - gap_start

            # Only add continuity for short gaps (< min_silence)
            if 0 < gap_duration < min_silence:
                continuity_ranges.append(TimeRange(start=gap_start, end=gap_end))

        # Merge continuity ranges with keep ranges
        all_keep = keep_ranges + continuity_ranges
        keep_ranges = _merge_ranges(all_keep, tolerance=0.01)

    # Step 4: Build silence ranges from gaps between segments >= min_silence
    silence_ranges: list[TimeRange] = []

    if segments:
        # Check for silence at the beginning
        if segments[0].start >= min_silence:
            silence_ranges.append(TimeRange(start=0.0, end=segments[0].start))

        # Gaps between segments
        for i in range(len(segments) - 1):
            gap_start = segments[i].end
            gap_end = segments[i + 1].start
            gap_duration = gap_end - gap_start

            if gap_duration >= min_silence:
                silence_ranges.append(TimeRange(start=gap_start, end=gap_end))

        # Check for silence at the end
        if total_duration > 0:
            last_end = segments[-1].end
            end_silence = total_duration - last_end
            if end_silence >= min_silence:
                silence_ranges.append(TimeRange(start=last_end, end=total_duration))
    elif total_duration > 0:
        # No segments, entire file is silence
        silence_ranges.append(TimeRange(start=0.0, end=total_duration))

    # Step 5: Subtract silences from keep ranges
    keep_ranges = _subtract_ranges(keep_ranges, silence_ranges)

    # Step 6: Convert keep ranges to cuts
    cuts = _ranges_to_cuts(keep_ranges, total_duration)

    return cuts


# ============================================================================
# Legacy API - kept for backward compatibility and tests
# ============================================================================

def detect_fillers(
    segments: list[Segment],
    language: str = "fr",
    custom_fillers: Optional[list[str]] = None
) -> list[Cut]:
    """
    Detect filler words in transcribed segments.

    This is the legacy API that detects fillers at word level and segment level.
    Kept for backward compatibility with existing tests and code.

    Args:
        segments: List of transcribed segments
        language: Language code ("fr" or "en")
        custom_fillers: Optional list of custom filler words to detect

    Returns:
        List of Cut objects representing filler word occurrences
    """
    # Build filler list
    fillers = DEFAULT_FILLERS.get(language, DEFAULT_FILLERS["en"])
    if custom_fillers:
        fillers = list(set(fillers + [f.lower().strip() for f in custom_fillers]))

    # Build regex pattern with word boundaries
    filler_patterns = _build_filler_patterns(fillers)

    cuts = []

    for segment in segments:
        # Word-level: use aligned words when available
        for word in segment.words:
            normalized_word = _normalize_word(word.word)
            for filler, pattern in filler_patterns.items():
                if pattern.match(normalized_word):
                    cuts.append(Cut(
                        start=word.start,
                        end=word.end,
                        cut_type="filler",
                        label=f"Filler: {word.word}"
                    ))
                    break

        # Segment-level fallback: when the whole segment is just a filler (e.g. "hmm...")
        # WhisperX sometimes doesn't return word-level alignment for short filler-only segments
        normalized_segment_text = _normalize_word(segment.text)
        if not normalized_segment_text:
            continue
        for filler, pattern in filler_patterns.items():
            if pattern.match(normalized_segment_text):
                cuts.append(Cut(
                    start=segment.start,
                    end=segment.end,
                    cut_type="filler",
                    label=f"Filler: {segment.text.strip()}"
                ))
                break

    return cuts
