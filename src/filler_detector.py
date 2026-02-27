"""Filler word detection in transcribed segments."""

import re
from typing import Optional

from src.models import Cut, Segment, Word


# Default filler words by language
DEFAULT_FILLERS = {
    "fr": ["euh", "ben", "du coup", "en fait", "bon", "bah", "quoi", "hmm", "tu vois"],
    "en": ["um", "uh", "like", "you know", "i mean", "basically", "so", "right"],
}

# Phonetic variants for common fillers
FILLER_VARIANTS = {
    "um": ["mm", "hm", "hmm", "umm"],
    "uh": ["ah", "uhh"],
    "euh": ["eu", "euu", "euhh"],
    "hmm": ["mm", "hm", "hmm", "mhm"],
    "quoi": ["ko", "kw"],
}


def detect_fillers(
    segments: list[Segment],
    language: str = "fr",
    custom_fillers: Optional[list[str]] = None
) -> list[Cut]:
    """
    Detect filler words in transcribed segments.

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
        for word in segment.words:
            normalized_word = _normalize_word(word.word)

            # Check against filler patterns
            for filler, pattern in filler_patterns.items():
                if pattern.match(normalized_word):
                    cuts.append(Cut(
                        start=word.start,
                        end=word.end,
                        cut_type="filler",
                        label=f"Filler: {word.word}"
                    ))
                    break

    return cuts


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
