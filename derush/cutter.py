"""Cutting pipeline V2 for the derush tool.

Token-centric approach:
- Source of truth: word_segments (flat list of all words with timestamps)
- A word is either "to keep" (content) or "to cut" (filler)
- We build a continuous timeline from kept words
- Tokens are merged into segments for export

Pipeline:
1. LOAD      → List[Word] (raw data from WhisperX)
2. CORRECT   → List[Word] (timings corrected based on word length)
3. CLASSIFY  → List[Word] (status: KEPT/FILLER)
4. FILTER    → List[Word] (only kept words)
5. TIMELINE  → List[TimelineToken] (continuous positions)
6. SEGMENTS  → List[TimelineSegment] (merged adjacent tokens)
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from derush.config import (
    DEFAULT_FILLERS,
    FILLER_VARIANTS,
    TIMING_3LETTER_MAX,
    TIMING_5LETTER_MAX,
    TIMING_8LETTER_MAX,
    TIMING_CHAR_SECONDS,
    TIMING_MAX_DURATION,
    TIMING_MAX_GAP_MERGE,
    TIMING_SHORT_WORD_MAX,
    CutterConfig,
)
from derush.exceptions import ValidationError
from derush.exporters.debug import DebugExporter
from derush.models import (
    Cut,
    CutReason,
    CutterResult,
    CutType,
    KeepSegment,
    PaddingStats,
    TimelineSegment,
    TimelineToken,
    Word,
    WordStatus,
)


# =============================================================================
# Step 1: LOAD - Parse WhisperX JSON
# =============================================================================


def load_whisperx_words(whisperx_path: Path) -> list[Word]:
    """Load words from WhisperX JSON file.

    Args:
        whisperx_path: Path to WhisperX JSON output

    Returns:
        List of Word objects with raw timings
    """
    with open(whisperx_path, encoding="utf-8") as f:
        data = json.load(f)

    # Extract word_segments (source of truth); fallback: build from segments[].words
    word_segments = data.get("word_segments", [])
    if not word_segments and data.get("segments"):
        for seg in data["segments"]:
            word_segments.extend(seg.get("words", []))

    # Convert to Word objects; validate structure
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

    return words


# =============================================================================
# Step 2: CORRECT - Fix abnormally long word durations
# =============================================================================


def estimate_word_duration(word: str) -> float:
    """Estimate expected duration for a word based on its length.

    Args:
        word: The word text

    Returns:
        Estimated duration in seconds
    """
    n = len(word.strip())
    if n <= 2:
        return TIMING_SHORT_WORD_MAX  # "le", "de", "je"
    if n <= 3:
        return TIMING_3LETTER_MAX  # "pas", "cas"
    if n <= 5:
        return TIMING_5LETTER_MAX  # "voiture"
    if n <= 8:
        return TIMING_8LETTER_MAX  # "maintenant"
    return min(TIMING_CHAR_SECONDS * n, TIMING_MAX_DURATION)


def correct_word_timestamps(words: list[Word]) -> tuple[list[Word], int]:
    """Correct misaligned word timestamps from WhisperX.

    Words with abnormally long duration (e.g., "test" lasting 4+ seconds)
    absorb silence/gaps that should be detected separately.
    This function truncates them to reasonable durations.

    Args:
        words: List of words with potentially incorrect timestamps

    Returns:
        Tuple of (corrected words list, count of corrections made)
    """
    if not words:
        return words, 0

    corrected_words = []
    corrected_count = 0

    for i, word in enumerate(words):
        duration = word.end - word.start
        max_duration = estimate_word_duration(word.word)

        # Check if duration exceeds expected
        if duration > max_duration:
            # Truncate the word's end time
            new_end = word.start + max_duration

            # Don't extend beyond the next word's start
            if i + 1 < len(words):
                next_word = words[i + 1]
                new_end = min(new_end, next_word.start - 0.001)

            # Don't extend beyond original end
            new_end = min(new_end, word.end)

            # Ensure minimum duration
            new_end = max(word.start + 0.05, new_end)

            corrected_word = Word(
                word=word.word,
                start=word.start,
                end=new_end,
                score=word.score,
                status=word.status,
            )
            corrected_words.append(corrected_word)
            corrected_count += 1
        else:
            corrected_words.append(word)

    return corrected_words, corrected_count


# =============================================================================
# Step 3: CLASSIFY - Mark filler words
# =============================================================================


def _normalize_word(word: str) -> str:
    """Normalize word for matching (lowercase, strip punctuation)."""
    return re.sub(r"[^\w\s]", "", word.lower()).strip()


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
    """Check if a word is a filler."""
    normalized = _normalize_word(word)
    if not normalized:
        return False
    return any(pattern.match(normalized) for pattern in filler_patterns.values())


def classify_words(
    words: list[Word], language: str = "fr", custom_fillers: list[str] | None = None
) -> list[Word]:
    """Classify each word as KEPT or FILLER.

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


# =============================================================================
# Step 4: FILTER - Keep only non-filler words
# =============================================================================


def filter_kept_words(words: list[Word]) -> list[Word]:
    """Filter to keep only non-filler words.

    Args:
        words: List of classified words

    Returns:
        List of words with status KEPT only
    """
    return [w for w in words if w.status == WordStatus.KEPT]


# =============================================================================
# Step 5: TIMELINE - Build continuous timeline from kept words
# =============================================================================


def build_timeline(
    words: list[Word], corrected_indices: set[int] | None = None
) -> list[TimelineToken]:
    """Build continuous timeline from kept words.

    Each token has:
    - Original position in source (original_start, original_end)
    - Position in final continuous timeline (timeline_start, timeline_end)

    Args:
        words: List of kept words (non-fillers)
        corrected_indices: Set of indices that were corrected (optional)

    Returns:
        List of TimelineToken with continuous timeline positions
    """
    tokens = []
    timeline_pos = 0.0

    for i, word in enumerate(words):
        duration = word.end - word.start
        was_corrected = corrected_indices is not None and i in corrected_indices

        token = TimelineToken(
            text=word.word,
            original_start=word.start,
            original_end=word.end,
            timeline_start=timeline_pos,
            timeline_end=timeline_pos + duration,
            corrected=was_corrected,
        )
        tokens.append(token)
        timeline_pos += duration

    return tokens


# =============================================================================
# Step 6: SEGMENTS - Merge adjacent tokens for export
# =============================================================================


def merge_adjacent_tokens(
    tokens: list[TimelineToken], max_gap: float = TIMING_MAX_GAP_MERGE
) -> list[TimelineSegment]:
    """Merge adjacent tokens in source into segments.

    Tokens that are close together in the source (< max_gap) are merged
    into a single segment to avoid excessive number of clips in FCPXML.

    Args:
        tokens: List of timeline tokens
        max_gap: Maximum gap in source to consider tokens adjacent

    Returns:
        List of TimelineSegment with merged tokens
    """
    if not tokens:
        return []

    segments = []
    current_start = tokens[0]

    for i in range(1, len(tokens)):
        prev = tokens[i - 1]
        curr = tokens[i]

        # Check gap in SOURCE (not timeline)
        gap_in_source = curr.original_start - prev.original_end

        if gap_in_source > max_gap:
            # Gap too large, finalize current segment
            segments.append(TimelineSegment(start_token=current_start, end_token=prev))
            current_start = curr

    # Finalize last segment
    segments.append(TimelineSegment(start_token=current_start, end_token=tokens[-1]))

    return segments


# =============================================================================
# Compatibility layer: Convert TimelineSegments to KeepSegments
# =============================================================================


def segments_to_keep_segments(segments: list[TimelineSegment]) -> list[KeepSegment]:
    """Convert TimelineSegments to KeepSegments for backward compatibility.

    Args:
        segments: List of TimelineSegment

    Returns:
        List of KeepSegment with same start/end times
    """
    return [
        KeepSegment(start=s.original_start, end=s.original_end)
        for s in segments
    ]


def compute_cuts_from_segments(
    segments: list[TimelineSegment], total_duration: float, words: list[Word]
) -> list[Cut]:
    """Compute cuts from segments (complement of keep segments).

    Args:
        segments: List of TimelineSegment to keep
        total_duration: Total media duration
        words: Original words list (for filler detection)

    Returns:
        List of Cut objects
    """
    if not segments:
        if total_duration > 0:
            return [
                Cut(
                    start=0.0,
                    end=total_duration,
                    cut_type=CutType.SILENCE,
                    reason=CutReason.GAP_BEFORE_SPEECH,
                )
            ]
        return []

    cuts = []
    current_pos = 0.0

    # Build filler ranges for type detection
    filler_ranges = [
        (w.start, w.end) for w in words if w.status == WordStatus.FILLER
    ]

    def has_filler(start: float, end: float) -> bool:
        """Check if a range contains a filler word."""
        for fs, fe in filler_ranges:
            if start < fe and end > fs:
                return True
        return False

    for segment in segments:
        if segment.original_start > current_pos:
            # Gap between current position and segment = cut
            cut_start = current_pos
            cut_end = segment.original_start

            if has_filler(cut_start, cut_end):
                cut_type = CutType.FILLER
                reason = CutReason.FILLER_WORD
            elif cut_start == 0.0:
                cut_type = CutType.SILENCE
                reason = CutReason.GAP_BEFORE_SPEECH
            else:
                cut_type = CutType.SILENCE
                reason = CutReason.GAP_BETWEEN_SEGMENTS

            cuts.append(Cut(start=cut_start, end=cut_end, cut_type=cut_type, reason=reason))

        current_pos = segment.original_end

    # Final cut after last segment
    if current_pos < total_duration:
        if has_filler(current_pos, total_duration):
            cut_type = CutType.FILLER
            reason = CutReason.FILLER_WORD
        else:
            cut_type = CutType.SILENCE
            reason = CutReason.GAP_AFTER_SPEECH
        cuts.append(Cut(start=current_pos, end=total_duration, cut_type=cut_type, reason=reason))

    return cuts


# =============================================================================
# Main pipeline
# =============================================================================


@dataclass
class PipelineResult:
    """Result of the V2 cutting pipeline."""

    # New V2 structures
    tokens: list[TimelineToken]
    segments: list[TimelineSegment]

    # Legacy structures (for backward compatibility)
    words: list[Word]
    cuts: list[Cut]
    keep_segments: list[KeepSegment]

    # Stats
    total_words: int
    kept_words: int
    filler_words: int
    corrected_words: int
    original_duration: float
    final_duration: float
    cut_duration: float
    padding_stats: PaddingStats | None = None

    @property
    def cut_percentage(self) -> float:
        """Percentage of the video that will be cut."""
        if self.original_duration == 0:
            return 0.0
        return (self.cut_duration / self.original_duration) * 100


def run_pipeline(
    whisperx_path: Path,
    total_duration: float,
    language: str = "fr",
    custom_fillers: list[str] | None = None,
    config: CutterConfig | None = None,
    debug_output: Path | None = None,
) -> CutterResult:
    """Run the full V2 cutting pipeline from WhisperX JSON.

    Pipeline:
    1. LOAD      → Load words from WhisperX JSON
    2. CORRECT   → Fix abnormally long word durations
    3. CLASSIFY  → Mark filler words
    4. FILTER    → Keep only non-filler words
    5. TIMELINE  → Build continuous timeline
    6. SEGMENTS  → Merge adjacent tokens

    Args:
        whisperx_path: Path to the WhisperX JSON file
        total_duration: Total duration of the media file
        language: Language code ("fr" or "en")
        custom_fillers: Optional list of custom filler words
        config: Optional cutter configuration
        debug_output: Optional path for debug JSON exports

    Returns:
        CutterResult with words, cuts, keep_segments, and summary
    """
    if config is None:
        config = CutterConfig()

    # Setup debug exporter if requested
    debug = DebugExporter(debug_output) if debug_output else None

    # Step 1: LOAD
    words = load_whisperx_words(whisperx_path)
    if debug:
        debug.export_loaded(words)

    # Step 2: CORRECT
    words, corrected_count = correct_word_timestamps(words)
    if debug:
        debug.export_corrected(words)

    # Track which words were corrected (for TimelineToken.corrected)
    corrected_indices = set()
    original_words = load_whisperx_words(whisperx_path)
    for i, (orig, corr) in enumerate(zip(original_words, words)):
        if orig.end != corr.end:
            corrected_indices.add(i)

    # Step 3: CLASSIFY
    words = classify_words(words, language, custom_fillers)
    if debug:
        debug.export_classified(words)

    # Step 4: FILTER
    kept_words = filter_kept_words(words)
    if debug:
        debug.export_filtered(kept_words)

    # Step 5: TIMELINE
    # Build mapping from kept words to their original indices
    kept_to_original = {}
    kept_idx = 0
    for i, w in enumerate(words):
        if w.status == WordStatus.KEPT:
            kept_to_original[kept_idx] = i
            kept_idx += 1

    tokens = build_timeline(kept_words)
    # Update corrected flag based on original indices
    for i, token in enumerate(tokens):
        orig_idx = kept_to_original.get(i)
        if orig_idx is not None and orig_idx in corrected_indices:
            token.corrected = True

    if debug:
        debug.export_timeline(tokens)

    # Step 6: SEGMENTS
    segments = merge_adjacent_tokens(tokens)
    if debug:
        debug.export_segments(segments)

    # Convert to legacy structures
    keep_segments = segments_to_keep_segments(segments)
    cuts = compute_cuts_from_segments(segments, total_duration, words)

    # Compute stats
    total_words = len(words)
    filler_words = sum(1 for w in words if w.status == WordStatus.FILLER)
    kept_words_count = total_words - filler_words

    cut_duration = sum(c.end - c.start for c in cuts)
    final_duration = total_duration - cut_duration

    return CutterResult(
        words=words,
        cuts=cuts,
        keep_segments=keep_segments,
        total_words=total_words,
        kept_words=kept_words_count,
        filler_words=filler_words,
        corrected_words=corrected_count,
        original_duration=total_duration,
        final_duration=final_duration,
        cut_duration=cut_duration,
        padding_stats=None,  # V2 doesn't use padding
    )
