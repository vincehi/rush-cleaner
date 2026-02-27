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
    
    # Maximum allowed word duration (seconds)
    # Words longer than this are considered misaligned and will be corrected
    max_word_duration: float = 2.0
    
    # Minimum confidence score for word alignment
    # Words with score below this threshold may have their timestamps adjusted
    min_word_score: float = 0.5


# Default filler words by language
# Only include true hesitation sounds/words that should always be cut
# Avoid words that can be content words in context
DEFAULT_FILLERS = {
    "fr": ["euh", "ben", "bah", "hmm", "bon ben", "euh", "euhh"],
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
