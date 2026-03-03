# Derush

Automatically detect silences and filler words in your videos. Export to DaVinci Resolve or Final Cut Pro for fast editing.

## Quick Start

**1. Install / update**
```bash
# macOS / Linux
curl -LsSf https://raw.githubusercontent.com/vincehi/rush-cleaner/main/install.sh | sh

# Windows (PowerShell)
irm https://raw.githubusercontent.com/vincehi/rush-cleaner/main/install.ps1 | iex
```

Install **FFmpeg** (required): `brew install ffmpeg` (macOS), `apt install ffmpeg` (Linux), `winget install FFmpeg` (Windows).

**2. Run**
```bash
derush my_video.mp4
```

**3. Import**
- **DaVinci Resolve**: File > Import > Timeline > Select `.fcpxml`
- **Final Cut Pro**: File > Import > XML > Select `.fcpxml`

**4. Edit** - Delete the detected segments on your timeline

That's it! Your video is ready to edit.

---

## Common Options

```bash
# French video
derush video.mp4 --lang fr

# Softer cuts (keep 0.1s padding on each side)
derush video.mp4 --cut-padding 0.1

# Detect shorter silences (0.3s instead of 0.5s)
derush video.mp4 --min-silence 0.3

# Preview without generating file
derush video.mp4 --preview

# Keep WhisperX JSON for debugging
derush video.mp4 --keep-whisperx

# Add custom filler words
derush video.mp4 --fillers "like,you know"
```

## All Options

| Option | Description | Default |
|--------|-------------|--------|
| `--output`, `-o` | Output file path | Next to video |
| `--format`, `-f` | `fcpxml` or `json` | `fcpxml` |
| `--lang`, `-l` | Language (`fr`, `en`) | auto-detected |
| `--min-silence` | Min silence to cut (seconds) | `0.5` |
| `--min-gap` | Min gap between words to cut | `0.3` |
| `--cut-padding` | Padding around cuts (seconds) | `0` |
| `--fillers` | Custom filler words | built-in list |
| `--preview` | Show summary, no file | - |
| `--keep-whisperx` | Keep WhisperX JSON file | deleted |
| `--verbose`, `-v` | Show detailed cuts | - |
| `--model`, `-m` | Whisper model size | `base` |
| `--device` | `cpu` or `cuda` | `cpu` |
| `--version`, `-V` | Show version | - |

## Filler Words Detected

**French**: euh, ben, bah, hmm, bon ben

**English**: um, uh, hmm

Add more with `--fillers "word1,word2"`.

## FAQ

**Q: I see a warning about "torchcodec" at startup**

It's harmless. Audio works fine via FFmpeg. To hide it, use `--vad silero`.

**Q: Premiere Pro?**

Premiere doesn't support FCPXML natively. Use [XtoCC](https://stupidpsoftware.com/xtocc/) to convert, or export as JSON.

**Q: How to uninstall?**

```bash
uv tool uninstall derush
```

## License

MIT License
