# Configuration Guide

## Environment Variables

You can configure derush using environment variables or a `.env` file.

### Available Variables

| Variable | Description | Default |
|----------|-------------|----------|
| `DERUSH_MIN_SILENCE` | Minimum silence duration in seconds to cut | 0.5 |
| `DERUSH_MIN_GAP_CUT` | Minimum gap between words to cut | 0.3 |
| `DERUSH_GAP_AFTER_FILLER` | Cut gaps after filler words | true |
| `DERUSH_MAX_WORD_DURATION` | Maximum word duration in seconds | 2.0 |
| `DERUSH_LANGUAGE` | Default language code | auto-detect |
| `DERUSH_MODEL` | Whisper model size | base |
| `DERUSH_DEVICE` | Device for transcription (cpu/cuda) | cpu |
| `DERUSH_CHUNK_SIZE` | VAD chunk size in seconds | 15 |

### Setup

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your preferences:
   ```bash
   # .env
   DERUSH_MIN_SILENCE=0.8
   DERUSH_LANGUAGE=fr
   ```

3. The CLI will automatically load variables from `.env` if it exists in the working directory.

### CLI Override

Environment variables can be overridden by CLI arguments:
```bash
# .env has DERUSH_MIN_SILENCE=0.8
derush input.mp4 --min-silence 0.5  # Uses 0.5, not 0.8
```
