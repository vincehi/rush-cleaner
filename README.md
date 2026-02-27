# Derush

Outil de dérushage vidéo automatique - Detectez les silences et filler words pour accelerer votre montage.

## Quick Start

```bash
# Installation
pip install -e ".[dev]"

# Utilisation basique
derush ma_video.mp4
```

Le fichier genere (`ma_video.fcpxml`) peut etre importe directement dans DaVinci Resolve, Final Cut Pro ou Premiere Pro.

## Prerequis

- **Python 3.10 a 3.13** (Python 3.14 non supporte par WhisperX)
- **FFmpeg** - `brew install ffmpeg` (macOS) ou `sudo apt install ffmpeg` (Ubuntu)

## Installation

```bash
# Cloner le projet
git clone https://github.com/vincentsourice/derush.git
cd derush

# Creer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/macOS

# Installer
pip install -e ".[dev]"

# Verifier
derush --help
```

## Utilisation

```bash
# Analyse basique (format FCPXML par defaut)
derush video.mp4

# Format EDL (Premiere Pro, Avid)
derush video.mp4 --format edl

# Specifier la langue
derush video.mp4 --lang fr

# Duree minimale de silence (secondes)
derush video.mp4 --min-silence 0.3

# Ajouter des filler words personnalises
derush video.mp4 --fillers "en fait,du coup,tu vois"

# Utiliser le GPU (CUDA)
derush video.mp4 --device cuda

# Modele Whisper plus precis (plus lent)
derush video.mp4 --model large
```

## Options

| Option | Description | Defaut |
|--------|-------------|--------|
| `--format`, `-f` | Format de sortie (`fcpxml`, `edl`, `json`) | `fcpxml` |
| `--lang`, `-l` | Langue (`fr`, `en`) | auto-detection |
| `--min-silence` | Duree min. silence (secondes) | `0.5` |
| `--fillers` | Filler words personnalises | - |
| `--fps` | Forcer le FPS | auto |
| `--model`, `-m` | Modele Whisper (`tiny`, `base`, `small`, `medium`, `large`) | `base` |
| `--device` | Appareil (`cpu`, `cuda`) | `cpu` |
| `--output`, `-o` | Fichier de sortie | auto |
| `--version`, `-v` | Afficher la version | - |

## Formats de sortie

### FCPXML 1.9
Compatible DaVinci Resolve, Final Cut Pro. Metadonnees riches avec types silence/filler.

### EDL (CMX3600)
Compatible DaVinci Resolve, Premiere Pro, Avid Media Composer. Standard de l'industrie.

### JSON
Pour debug ou integrations personnalisees.

## Workflow

1. Enregistrez votre video brute
2. Lancez `derush video.mp4`
3. Importez le fichier genere dans votre logiciel de montage
4. Supprimez les segments detectes sur votre timeline

## Filler words detectes

**Francais** : euh, ben, du coup, en fait, bon, bah, quoi, tu vois

**Anglais** : um, uh, like, you know, I mean, basically, so, right

## Tests

```bash
pytest tests/ -v
pytest tests/ --cov=src --cov-report=html
```

## Licence

MIT License - voir [LICENSE](LICENSE)

---

Cree pour les createurs de contenu qui veulent passer moins de temps a derusher.
