"""Cutting pipeline for the derush tool.

This module implements the "keep segments" approach:
- Source of truth: word_segments (flat list of all words with timestamps)
- A word is either "to keep" (content) or "to cut" (filler)
- We compute cuts from fillers and gaps, then derive keep segments
"""

import json
import re
from pathlib import Path
from typing import Optional

from derush.config import CutterConfig, DEFAULT_FILLERS, FILLER_VARIANTS
from derush.models import (
    Cut,
    CutterResult,
    CutReason,
    CutType,
    KeepSegment,
    Word,
    WordStatus,
    merge_adjacent_cuts,
)


# Timing constants (in seconds)
MINIMUM_WORD_DURATION = 0.05  # 50ms minimum duration
MINIMUM_GAP_THRESHOLD = 0.01   # 10ms minimum gap to cut
WORD_OVERLAP_BUFFER = 0.001    # 1ms buffer between words


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


def correct_word_timestamps(
    words: list[Word],
    config: CutterConfig
) -> list[Word]:
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
        List of words with corrected timestamps
    """
    if not words:
        return words
    
    corrected_words = []
    
    for i, word in enumerate(words):
        duration = word.end - word.start
        
        # Check if this word needs correction
        needs_correction = (
            duration > config.max_word_duration or
            word.score < config.min_word_score
        )
        
        if needs_correction:
            # Get expected duration for this word
            normalized = _normalize_word(word.word)
            expected_duration = AVERAGE_WORD_DURATIONS.get(normalized)
            
            # If no known average, estimate based on word length
            if expected_duration is None:
                # Rough estimate: ~0.1s per character, max 0.5s for content words
                # Fillers are typically shorter
                char_count = len(normalized)
                expected_duration = min(0.08 * char_count, 0.5)
            
            # Truncate the word's end time if it's too long
            new_end = word.start + expected_duration
            
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
                status=word.status
            )
            corrected_words.append(corrected_word)
        else:
            corrected_words.append(word)
    
    return corrected_words


def _build_filler_patterns(fillers: list[str]) -> dict[str, re.Pattern]:
    """Build regex patterns for filler matching with word boundaries."""
    patterns = {}
    for filler in fillers:
        variants = set([filler])
        
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
    words: list[Word],
    language: str = "fr",
    custom_fillers: Optional[list[str]] = None
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


def compute_cuts(
    words: list[Word],
    config: CutterConfig,
    total_duration: float
) -> list[Cut]:
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
            cuts.append(Cut(
                start=0.0,
                end=total_duration,
                cut_type=CutType.SILENCE,
                reason=CutReason.GAP_BEFORE_SPEECH
            ))
        return cuts

    # Get kept words only (non-fillers)
    kept_words = [w for w in words if w.status == WordStatus.KEPT]
    filler_words = [w for w in words if w.status == WordStatus.FILLER]

    # 1. Cut silences at the beginning (before first word)
    first_word = words[0]
    if first_word.start >= config.min_silence:
        cuts.append(Cut(
            start=0.0,
            end=first_word.start,
            cut_type=CutType.SILENCE,
            reason=CutReason.GAP_BEFORE_SPEECH
        ))

    # 2. Cut silences at the end (after last word)
    last_word = words[-1]
    end_silence = total_duration - last_word.end
    if end_silence >= config.min_silence:
        cuts.append(Cut(
            start=last_word.end,
            end=total_duration,
            cut_type=CutType.SILENCE,
            reason=CutReason.GAP_AFTER_SPEECH
        ))

    # 3. Cut filler words
    for filler in filler_words:
        cuts.append(Cut(
            start=filler.start,
            end=filler.end,
            cut_type=CutType.FILLER,
            reason=CutReason.FILLER_WORD,
            word=filler.word
        ))

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
                    cuts.append(Cut(
                        start=gap_start,
                        end=gap_end,
                        cut_type=CutType.GAP,
                        reason=CutReason.GAP_AFTER_FILLER
                    ))

    # 5. Cut gaps between segments
    for i in range(len(words) - 1):
        current = words[i]
        next_word = words[i + 1]
        gap_duration = next_word.start - current.end

        # Large gap = segment boundary
        if gap_duration >= config.min_silence:
            cuts.append(Cut(
                start=current.end,
                end=next_word.start,
                cut_type=CutType.SILENCE,
                reason=CutReason.GAP_BETWEEN_SEGMENTS
            ))

    # 6. Merge adjacent cuts
    cuts = merge_adjacent_cuts(cuts)

    return cuts


def compute_keep_segments(
    cuts: list[Cut],
    total_duration: float
) -> list[KeepSegment]:
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
    custom_fillers: Optional[list[str]] = None,
    config: Optional[CutterConfig] = None,
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
    with open(whisperx_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract word_segments (source of truth)
    word_segments = data.get("word_segments", [])

    # Convert to Word objects
    words = [
        Word(
            word=ws["word"],
            start=ws["start"],
            end=ws["end"],
            score=ws.get("score", 1.0)
        )
        for ws in word_segments
    ]

    # Step 0: Correct misaligned timestamps from WhisperX
    words = correct_word_timestamps(words, config)

    # Step 1: Classify words
    words = classify_words(words, language, custom_fillers)

    # Step 2: Compute cuts
    cuts = compute_cuts(words, config, total_duration)

    # Step 3: Compute keep segments
    keep_segments = compute_keep_segments(cuts, total_duration)

    # Compute summary stats
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
        original_duration=total_duration,
        final_duration=final_duration,
        cut_duration=cut_duration,
    )
