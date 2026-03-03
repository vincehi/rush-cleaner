"""Configuration parameters for the derush tool."""

from dataclasses import dataclass


@dataclass
class CutterConfig:
    """Configuration for the cutting algorithm."""

    # Minimum silence duration to cut (seconds)
    # Silences shorter than this are kept (natural breathing)
    min_silence: float = 0.5

    # Minimum gap between CONTENT words to cut (seconds)
    # Gaps shorter than this are kept (natural speech flow)
    min_gap_cut: float = 0.3

    # Always cut gap after a filler word
    # Filler + pause = hesitation, should be removed
    gap_after_filler: bool = True

    # Padding (seconds) to leave at each side of a cut.
    # Reduces the cut by this amount on both sides so transitions are less abrupt.
    # E.g. 0.1 = keep 0.1s before and 0.1s after each cut boundary.
    cut_padding: float = 0.0

    # Minimum duration for a keep segment (seconds)
    # Segments shorter than this are merged with adjacent cuts to avoid micro-clips
    # that look jarring in the final video. Default 0.5s = ~15 frames at 30fps.
    min_keep_segment: float = 0.5


# =============================================================================
# Timing estimation constants (V2 pipeline)
# =============================================================================

# Duration estimation based on word length (in seconds)
# Used to correct abnormally long words from WhisperX
TIMING_SHORT_WORD_MAX = 0.15  # Words with 1-2 letters: "le", "de", "je"
TIMING_3LETTER_MAX = 0.20  # 3 letters: "pas", "cas"
TIMING_5LETTER_MAX = 0.35  # 4-5 letters: "voiture"
TIMING_8LETTER_MAX = 0.55  # 6-8 letters: "maintenant"
TIMING_CHAR_SECONDS = 0.08  # Seconds per character for longer words
TIMING_MAX_DURATION = 1.5  # Maximum duration cap for any word

# Gap tolerance for merging adjacent tokens in timeline (seconds)
TIMING_MAX_GAP_MERGE = 0.05  # Tokens with gap < this are merged into one segment


# =============================================================================
# Filler words
# =============================================================================

# Default filler words by language
# Only include true hesitation sounds/words that should always be cut
# Avoid words that can be content words in context
DEFAULT_FILLERS = {
    "fr": ["euh", "ben", "bah", "hmm", "bon ben", "euhh"],
    "en": ["um", "uh", "hmm", "umm", "uhh"],
}

# Phonetic variants for common fillers
# Whisper often transcribes prolonged sounds with extra letters
FILLER_VARIANTS = {
    "um": ["mm", "hm", "hmm", "umm", "ummm", "ummmm"],
    "uh": ["ah", "uhh", "uhhh"],
    "euh": ["eu", "euu", "euhh", "euhhh"],
    "hmm": ["mm", "hm", "mhm", "hmmm", "hmmmm", "hmmmmm"],
}
