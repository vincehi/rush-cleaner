"""Cutting pipeline for the derush tool.

This module implements the "keep segments" approach:
- Source of truth: word_segments (flat list of all words with timestamps)
- A word is either "to keep" (content) or "to cut" (filler)
- We compute cuts from fillers and gaps, then derive keep segments
"""

import json
import re
from pathlib import Path

from derush.config import DEFAULT_FILLERS, FILLER_VARIANTS, CutterConfig
from derush.exceptions import ValidationError
from derush.models import (
    Cut,
    CutReason,
    CutterResult,
    CutType,
    KeepSegment,
    PaddingStats,
    Word,
    WordStatus,
    merge_adjacent_cuts,
)

# Timing constants (in seconds)
MINIMUM_WORD_DURATION = 0.05  # 50ms minimum duration
MINIMUM_GAP_THRESHOLD = 0.01  # 10ms minimum gap to cut
WORD_OVERLAP_BUFFER = 0.001  # 1ms buffer between words


# Average word durations for common words (in seconds)
# Used to correct abnormally long words
AVERAGE_WORD_DURATIONS = {
    # French fillers - typically short
    "euh": 0.3,
    "ben": 0.3,
    "bah": 0.3,
    "hmm": 0.15,
    "voilà": 0.5,
    # Common short words
    "de": 0.15,
    "le": 0.15,
    "la": 0.15,
    "je": 0.15,
    "que": 0.2,
    "par": 0.2,
    "ton": 0.25,
}


def _normalize_word(word: str) -> str:
    """Normalize word for matching (lowercase, strip punctuation)."""
    return re.sub(r"[^\w\s]", "", word.lower()).strip()


def correct_word_timestamps(words: list[Word], config: CutterConfig) -> tuple[list[Word], int]:
    """
    Correct misaligned word timestamps from WhisperX.

    Handles two common issues:
    1. Words with abnormally long duration (e.g., "test" lasting 4+ seconds)
       - These absorb silence/gaps that should be detected separately
    2. Words with very low confidence scores (< 0.5)
       - These often have incorrect timestamps

    Strategy:
    - For words longer than max_word_duration, truncate them to a reasonable duration
    - Use average durations for common words, or a default max duration
    - This exposes hidden gaps/silences for proper detection

    Args:
        words: List of words with potentially incorrect timestamps
        config: Configuration with max_word_duration and min_word_score

    Returns:
        Tuple of (corrected words list, count of corrections made)
    """
    if not words:
        return words, 0

    corrected_words = []
    corrected_count = 0

    for i, word in enumerate(words):
        duration = word.end - word.start

        # Get expected/max duration for this word based on length
        normalized = _normalize_word(word.word)
        max_duration = AVERAGE_WORD_DURATIONS.get(normalized)

        # If no known average, estimate max duration based on word length
        if max_duration is None:
            char_count = len(normalized)
            if char_count <= 3:
                max_duration = 0.3  # Short words: "cas", "le", "de"
            elif char_count <= 5:
                max_duration = 0.4  # Medium-short: "voiture"
            elif char_count <= 8:
                max_duration = 0.6  # Medium: "maintenant"
            elif char_count <= 12:
                max_duration = 0.8  # Long: "ordinateur"
            else:
                max_duration = 1.0  # Very long: "anticonstitutionnellement"

        # Correct if duration exceeds max (regardless of score)
        needs_correction = duration > max_duration

        if needs_correction:
            # Truncate the word's end time
            new_end = word.start + max_duration

            # Don't extend beyond the next word's start
            if i + 1 < len(words):
                next_word = words[i + 1]
                new_end = min(new_end, next_word.start - WORD_OVERLAP_BUFFER)

            # Don't extend beyond original end
            new_end = min(new_end, word.end)

            corrected_word = Word(
                word=word.word,
                start=word.start,
                end=max(word.start + MINIMUM_WORD_DURATION, new_end),
                score=word.score,
                status=word.status,
            )
            corrected_words.append(corrected_word)
            corrected_count += 1
        else:
            corrected_words.append(word)

    return corrected_words, corrected_count


def _build_filler_patterns(fillers: list[str]) -> dict[str, re.Pattern]:
    """Build regex patterns for filler matching with word boundaries."""
    patterns = {}
    for filler in fillers:
        variants = {filler}

        for base, vars_list in FILLER_VARIANTS.items():
            if filler == base or filler in vars_list:
                variants.update([base] + vars_list)

        pattern_str = r"^(?:" + "|".join(re.escape(v) for v in variants) + r")$"
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

    return any(pattern.match(normalized) for pattern in filler_patterns.values())


def classify_words(
    words: list[Word], language: str = "fr", custom_fillers: list[str] | None = None
) -> list[Word]:
    """
    Classify each word as KEPT or FILLER.

    Args:
        words: List of words to classify
        language: Language code ("fr" or "en")
        custom_fillers: Optional list of custom filler words

    Returns:
        List of words with status set
    """
    # Build filler patterns
    fillers = DEFAULT_FILLERS.get(language, DEFAULT_FILLERS["en"])
    if custom_fillers:
        fillers = list(set(fillers + [f.lower().strip() for f in custom_fillers]))
    filler_patterns = _build_filler_patterns(fillers)

    for word in words:
        if is_filler(word.word, filler_patterns):
            word.status = WordStatus.FILLER
        else:
            word.status = WordStatus.KEPT

    return words


def compute_cuts(words: list[Word], config: CutterConfig, total_duration: float) -> list[Cut]:
    """
    Compute cuts based on classified words and gaps.

    Algorithm:
    1. Cuts from silences (gaps at start/end and between segments)
    2. Cuts from filler words
    3. Cuts from gaps after fillers (if enabled)
    4. Merge adjacent cuts

    Args:
        words: List of classified words
        config: Cutter configuration
        total_duration: Total duration of the media

    Returns:
        List of cuts to apply
    """
    cuts: list[Cut] = []

    if not words:
        # No words = entire file is silence
        if total_duration > 0:
            cuts.append(
                Cut(
                    start=0.0,
                    end=total_duration,
                    cut_type=CutType.SILENCE,
                    reason=CutReason.GAP_BEFORE_SPEECH,
                )
            )
        return cuts

    # Get kept words only (non-fillers)
    filler_words = [w for w in words if w.status == WordStatus.FILLER]

    # 1. Cut silences at the beginning (before first word)
    first_word = words[0]
    if first_word.start >= config.min_silence:
        cuts.append(
            Cut(
                start=0.0,
                end=first_word.start,
                cut_type=CutType.SILENCE,
                reason=CutReason.GAP_BEFORE_SPEECH,
            )
        )

    # 2. Cut silences at the end (after last word)
    last_word = words[-1]
    end_silence = total_duration - last_word.end
    if end_silence >= config.min_silence:
        cuts.append(
            Cut(
                start=last_word.end,
                end=total_duration,
                cut_type=CutType.SILENCE,
                reason=CutReason.GAP_AFTER_SPEECH,
            )
        )

    # 3. Cut filler words
    for filler in filler_words:
        cuts.append(
            Cut(
                start=filler.start,
                end=filler.end,
                cut_type=CutType.FILLER,
                reason=CutReason.FILLER_WORD,
                word=filler.word,
            )
        )

    # 4. Cut gaps after fillers (if enabled)
    if config.gap_after_filler:
        for i, word in enumerate(words):
            if word.status != WordStatus.FILLER:
                continue
            # Check if there's a next word
            if i + 1 < len(words):
                next_word = words[i + 1]
                gap_start = word.end
                gap_end = next_word.start
                gap_duration = gap_end - gap_start

                # Only cut if there's an actual gap
                if gap_duration > MINIMUM_GAP_THRESHOLD:
                    cuts.append(
                        Cut(
                            start=gap_start,
                            end=gap_end,
                            cut_type=CutType.GAP,
                            reason=CutReason.GAP_AFTER_FILLER,
                        )
                    )

    # 5. Cut gaps between segments (use min_gap_cut: threshold for gaps between any two words)
    for i in range(len(words) - 1):
        current = words[i]
        next_word = words[i + 1]
        gap_duration = next_word.start - current.end

        if gap_duration >= config.min_gap_cut:
            cuts.append(
                Cut(
                    start=current.end,
                    end=next_word.start,
                    cut_type=CutType.SILENCE,
                    reason=CutReason.GAP_BETWEEN_SEGMENTS,
                )
            )

    # 6. Merge adjacent cuts
    cuts = merge_adjacent_cuts(cuts)

    return cuts


def apply_cut_padding(
    cuts: list[Cut], padding: float, total_duration: float
) -> tuple[list[Cut], PaddingStats]:
    """
    Shrink each cut by a padding on both sides (keep a small buffer at cut boundaries).

    This leaves a short amount of time at the start/end of each cut in the
    "keep" segments, so transitions are less abrupt.

    Behavior:
    - Cuts long enough (duration > 2*padding + MIN_PADDING_REMAINING) are shrunk normally
    - Cuts too short are LEFT UNCHANGED (predictable behavior for user)
    - Edge silences (start/end of media) are never padded

    Args:
        cuts: List of cuts (sorted, non-overlapping)
        padding: Seconds to remove from each side of every cut (0 = no change)
        total_duration: Total media duration for clamping

    Returns:
        Tuple of (padded cuts, padding statistics)
    """
    stats = PaddingStats()

    if padding <= 0 or not cuts:
        return cuts, stats

    # Minimum remaining duration after padding (50ms)
    MIN_PADDING_REMAINING = 0.05
    # Minimum cut duration to be eligible for padding
    MIN_CUT_FOR_PADDING = 2 * padding + MIN_PADDING_REMAINING

    result: list[Cut] = []

    for cut in cuts:
        original_duration = cut.end - cut.start

        # Edge silences are never padded (would reintroduce content at edges)
        is_edge_silence = cut.reason in (
            CutReason.GAP_BEFORE_SPEECH,
            CutReason.GAP_AFTER_SPEECH,
        )

        if is_edge_silence:
            # Edge silences stay unchanged, don't count in stats
            result.append(cut)
            continue

        # Check if cut is long enough to be padded
        if original_duration < MIN_CUT_FOR_PADDING:
            # Too short - leave unchanged
            result.append(cut)
            stats.unchanged_count += 1
            continue

        # Apply padding normally
        new_start = cut.start + padding
        new_end = cut.end - padding

        # Safety clamping (should not happen with proper input)
        new_start = max(0.0, min(new_start, total_duration))
        new_end = max(new_start + MIN_PADDING_REMAINING, min(new_end, total_duration))

        result.append(
            Cut(
                start=new_start,
                end=new_end,
                cut_type=cut.cut_type,
                reason=cut.reason,
                word=cut.word,
            )
        )
        stats.padded_count += 1
        stats.duration_regained += 2 * padding

    return result, stats


def compute_keep_segments(cuts: list[Cut], total_duration: float) -> list[KeepSegment]:
    """
    Compute segments to keep from cuts (complement of cuts).

    Args:
        cuts: List of cuts (sorted, non-overlapping)
        total_duration: Total duration of the media

    Returns:
        List of segments to keep
    """
    if not cuts:
        if total_duration > 0:
            return [KeepSegment(start=0.0, end=total_duration)]
        return []

    keep_segments: list[KeepSegment] = []

    # Segment before first cut
    if cuts[0].start > 0:
        keep_segments.append(KeepSegment(start=0.0, end=cuts[0].start))

    # Segments between cuts
    for i in range(len(cuts) - 1):
        gap_start = cuts[i].end
        gap_end = cuts[i + 1].start
        if gap_end > gap_start:
            keep_segments.append(KeepSegment(start=gap_start, end=gap_end))

    # Segment after last cut
    if cuts[-1].end < total_duration:
        keep_segments.append(KeepSegment(start=cuts[-1].end, end=total_duration))

    return keep_segments


def run_pipeline(
    whisperx_path: Path,
    total_duration: float,
    language: str = "fr",
    custom_fillers: list[str] | None = None,
    config: CutterConfig | None = None,
) -> CutterResult:
    """
    Run the full cutting pipeline from WhisperX JSON.

    Args:
        whisperx_path: Path to the WhisperX JSON file
        total_duration: Total duration of the media file
        language: Language code ("fr" or "en")
        custom_fillers: Optional list of custom filler words
        config: Optional cutter configuration (uses defaults if not provided)

    Returns:
        CutterResult with words, cuts, keep_segments, and summary
    """
    if config is None:
        config = CutterConfig()

    # Load WhisperX data
    with open(whisperx_path, encoding="utf-8") as f:
        data = json.load(f)

    # Extract word_segments (source of truth); fallback: build from segments[].words
    word_segments = data.get("word_segments", [])
    if not word_segments and data.get("segments"):
        for seg in data["segments"]:
            word_segments.extend(seg.get("words", []))

    # Convert to Word objects; validate structure to avoid cryptic KeyError
    words = []
    for i, ws in enumerate(word_segments):
        try:
            words.append(
                Word(
                    word=str(ws.get("word", "")),
                    start=float(ws["start"]),
                    end=float(ws["end"]),
                    score=float(ws.get("score", 1.0)),
                )
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ValidationError(
                f"Invalid WhisperX format in {whisperx_path}:\n"
                f"  - Word at index {i} missing 'start' or 'end'\n"
                f"  - Verify that WhisperX ran correctly\n"
                f"  Detail: {e}"
            ) from e

    # Step 0: Correct misaligned timestamps from WhisperX
    words, corrected_count = correct_word_timestamps(words, config)

    # Step 1: Classify words
    words = classify_words(words, language, custom_fillers)

    # Step 2: Compute cuts
    cuts = compute_cuts(words, config, total_duration)

    # Step 2b: Apply padding so a small buffer is kept at each cut boundary
    cuts, padding_stats = apply_cut_padding(cuts, config.cut_padding, total_duration)

    # Step 3: Compute keep segments (from padded cuts)
    keep_segments = compute_keep_segments(cuts, total_duration)

    # Compute summary stats (from final cuts after padding)
    total_words = len(words)
    filler_words = sum(1 for w in words if w.status == WordStatus.FILLER)
    kept_words = total_words - filler_words

    cut_duration = sum(c.end - c.start for c in cuts)
    final_duration = total_duration - cut_duration

    return CutterResult(
        words=words,
        cuts=cuts,
        keep_segments=keep_segments,
        total_words=total_words,
        kept_words=kept_words,
        filler_words=filler_words,
        corrected_words=corrected_count,
        original_duration=total_duration,
        final_duration=final_duration,
        cut_duration=cut_duration,
        padding_stats=padding_stats if config.cut_padding > 0 else None,
    )
