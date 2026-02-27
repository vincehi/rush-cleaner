"""Transcription module using WhisperX."""

import json
from pathlib import Path
from typing import Optional

from derush.models import Segment, Word

# Hotwords to bias Whisper toward transcribing filler words (improves detection)
FILLER_HOTWORDS = (
    "hmm euh um uh ben quoi bah du coup en fait bon tu vois like you know"
)


def transcribe(
    file_path: Path,
    language: Optional[str] = None,
    model_size: str = "base",
    device: str = "cpu",
    chunk_size: int = 15,
    whisperx_output: Optional[Path] = None,
) -> list[Segment]:
    """
    Transcribe audio/video file using WhisperX with word-level alignment.

    Uses chunk_size < 30 and hotwords so that filler words (e.g. "hmm", "euh")
    are more likely to appear in the transcription and get word-level timestamps.

    Args:
        file_path: Path to the media file
        language: Language code (e.g., "fr", "en"). If None, auto-detect.
        model_size: Whisper model size ("tiny", "base", "small", "medium", "large-v2", "large-v3")
        device: Device to use ("cpu" or "cuda")
        chunk_size: Max duration (seconds) for merged VAD chunks. Default 15 gives more
            segments than WhisperX default (30), so short fillers are less often merged away.
        whisperx_output: Optional path to save the raw WhisperX result as JSON.

    Returns:
        List of transcribed segments with word-level timestamps

    Raises:
        FileNotFoundError: If the input file doesn't exist
        RuntimeError: If transcription fails
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Media file not found: {file_path}")

    # Import whisperx here to allow module to load without it installed
    try:
        import whisperx
    except ImportError:
        raise RuntimeError(
            "whisperx is not installed. Install it with: pip install whisperx"
        )

    # Compute type based on device
    compute_type = "float16" if device == "cuda" else "int8"

    # Options to improve filler word transcription (see WhisperX/faster-whisper docs)
    asr_options = {
        "hotwords": FILLER_HOTWORDS,  # bias model toward transcribing these words
        "no_speech_threshold": 0.5,   # keep short segments (default 0.6 can drop fillers)
    }
    vad_options = {"chunk_size": chunk_size}

    # Load model
    model = whisperx.load_model(
        model_size,
        device=device,
        compute_type=compute_type,
        asr_options=asr_options,
        vad_options=vad_options,
    )

    # Load audio
    audio = whisperx.load_audio(str(file_path))

    # Transcribe with same chunk_size so VAD produces more, shorter segments
    result = model.transcribe(audio, language=language, chunk_size=chunk_size)

    # Detect language from result if not specified
    detected_language = result.get("language", language if language else "en")

    # Align for word-level timestamps
    model_a, metadata = whisperx.load_align_model(
        language_code=detected_language,
        device=device
    )
    result = whisperx.align(
        result["segments"],
        model_a,
        metadata,
        audio,
        device,
        return_char_alignments=False
    )

    # Add detected language to result for output
    result["language"] = detected_language

    # Save raw WhisperX result if requested
    if whisperx_output:
        whisperx_output = Path(whisperx_output)
        whisperx_output.parent.mkdir(parents=True, exist_ok=True)
        with open(whisperx_output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    # Convert to our Segment format
    segments = []
    for seg in result.get("segments", []):
        words = []
        for w in seg.get("words", []):
            words.append(Word(
                word=w.get("word", ""),
                start=w.get("start", 0.0),
                end=w.get("end", 0.0),
                score=w.get("score", 0.0)
            ))

        segments.append(Segment(
            start=seg.get("start", 0.0),
            end=seg.get("end", 0.0),
            text=seg.get("text", "").strip(),
            words=words
        ))

    return segments
