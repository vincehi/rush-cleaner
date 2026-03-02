# Derush

Automatic video derushing tool - Detect silences and filler words to speed up your editing workflow.

## Installation

One command (installs [uv](https://docs.astral.sh/uv/) then derush — no Python needed):

**macOS / Linux:**
```bash
curl -LsSf https://raw.githubusercontent.com/vincehi/rush-cleaner/main/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/vincehi/rush-cleaner/main/install.ps1 | iex
```

Then: install **FFmpeg** (required to read videos) — `brew install ffmpeg` (macOS), `apt install ffmpeg` (Linux), `winget install FFmpeg` (Windows).
If `derush` is not found: add it to PATH (`$HOME/.local/bin` on macOS/Linux; restart terminal on Windows).

## Uninstall

```bash
uv tool uninstall derush
```
(uv must be in PATH.)

## Quick Start

```bash
derush my_video.mp4
```

The generated file (FCPXML by default) is created **next to the video** (same folder, same name with `.fcpxml` extension). Import it into DaVinci Resolve, FCP or Premiere. Dev details and commands: **[PYTHON.md](PYTHON.md)**.

## Requirements

- **FFmpeg** (required, install separately). No Python required.

## Troubleshooting

**torchcodec / Pyannote warning**: At startup, you may see a long warning like "torchcodec is not installed correctly so built-in audio decoding will fail". It comes from Pyannote (voice detection used by WhisperX). Audio is actually loaded via FFmpeg, so the software works; the message just indicates an environment issue.

To remove the warning (recommended):
- **Option A**: Align PyTorch / TorchCodec / FFmpeg versions using the [TorchCodec compatibility table](https://github.com/pytorch/torchcodec?tab=readme-ov-file#installing-torchcodec), or install a compatible FFmpeg version (e.g. `brew install ffmpeg` and verify libs are found).
- **Option B**: Use Silero VAD: `derush video.mp4 --vad silero` (or `vad_method="silero"` via Python API).

## Web Interface (GUI)

For a graphical interface in your browser (file upload, settings, Run button):

```bash
pip install derush[ui]   # once
derush ui
```

Opens a local page (default http://127.0.0.1:7860). Use `--share` for a temporary public link, `--port 8080` to change port.

## Usage (CLI)

```bash
# Basic analysis (FCPXML format by default)
derush video.mp4

# Specify language
derush video.mp4 --lang fr

# Minimum silence duration (seconds)
derush video.mp4 --min-silence 0.3

# Padding around cuts (seconds) to soften transitions
derush video.mp4 --cut-padding 0.1

# Add custom filler words
derush video.mp4 --fillers "like,you know,I mean"

# Use GPU (CUDA)
derush video.mp4 --device cuda

# More accurate Whisper model (slower)
derush video.mp4 --model large

# Preview without generating file (dry-run)
derush video.mp4 --preview

# Detailed logs (cut decisions)
derush video.mp4 --verbose
```

## Options

| Option | Description | Default |
|--------|-------------|--------|
| `--output`, `-o` | Output file | Next to video (same name, .fcpxml or .json) |
| `--format`, `-f` | Output format (`fcpxml`, `json`) | `fcpxml` |
| `--lang`, `-l` | Language (`fr`, `en`). Auto-detected from transcription if not specified | auto |
| `--min-silence` | Min. silence duration to cut (seconds) | `0.5` |
| `--min-gap` | Min. gap between words to cut (seconds) | `0.3` |
| `--cut-padding` | Seconds to keep on each side of cuts (softens transitions; cuts too short are left unchanged) | `0` |
| `--fillers` | Custom filler words (comma-separated) | per-language list |
| `--preview` | Show summary without generating file | - |
| `--verbose`, `-v` | Show cut decisions (words, segments) | - |
| `--fps` | Force FPS | auto (or 25) |
| `--model`, `-m` | Whisper model (`tiny`, `base`, `small`, `medium`, `large`) | `base` |
| `--vad` | VAD backend: `pyannote` or `silero` (silero avoids torchcodec warning) | `pyannote` |
| `--chunk-size` | Max VAD segment size (seconds); smaller = more segments | `15` |
| `--device` | Device (`cpu`, `cuda`) | `cpu` |
| `--version`, `-V` | Show version and exit | - |

## Output Formats

### FCPXML 1.9
Compatible with DaVinci Resolve, Final Cut Pro. Rich metadata with silence/filler types.

### JSON
For debugging or custom integrations.

## Workflow

1. Record your raw video
2. Run `derush video.mp4`
3. Import the generated file into your editing software
4. Delete detected segments on your timeline

## Filler Words (default)

List defined in `derush.config.DEFAULT_FILLERS` by language:

**French** (`--lang fr`): euh, ben, bah, hmm, bon ben (and variants)

**English** (`--lang en` or unspecified): um, uh, hmm (and variants)

To add more (e.g. "you know", "like"): `--fillers "you know,like"`.

## Tests

```bash
make test
# or with coverage
./venv/bin/pytest tests/ -v --cov=derush --cov-report=html
```

## License

MIT License - see [LICENSE](LICENSE)

---

Built for content creators who want to spend less time derushing.
