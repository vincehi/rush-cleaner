"""Transcription module using WhisperX."""

from pathlib import Path
from typing import Optional

from src.models import Segment, Word


def transcribe(
    file_path: Path,
    language: Optional[str] = None,
    model_size: str = "base",
    device: str = "cpu"
) -> list[Segment]:
    """
    Transcribe audio/video file using WhisperX with word-level alignment.

    Args:
        file_path: Path to the media file
        language: Language code (e.g., "fr", "en"). If None, auto-detect.
        model_size: Whisper model size ("tiny", "base", "small", "medium", "large-v2", "large-v3")
        device: Device to use ("cpu" or "cuda")

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

    # Load model
    model = whisperx.load_model(
        model_size,
        device=device,
        compute_type=compute_type
    )

    # Load audio
    audio = whisperx.load_audio(str(file_path))

    # Transcribe
    result = model.transcribe(audio, language=language)

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
