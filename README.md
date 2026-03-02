# Derush

Outil de dérushage vidéo automatique - Detectez les silences et filler words pour accelerer votre montage.

## Installation

Une commande (installe [uv](https://docs.astral.sh/uv/) puis derush — pas besoin de Python) :

**macOS / Linux :**
```bash
curl -LsSf https://raw.githubusercontent.com/vincehi/rush-cleaner/main/install.sh | sh
```

**Windows (PowerShell) :**
```powershell
irm https://raw.githubusercontent.com/vincehi/rush-cleaner/main/install.ps1 | iex
```

Ensuite : installer **FFmpeg** (requis pour lire les vidéos) — `brew install ffmpeg` (macOS), `apt install ffmpeg` (Linux), `winget install FFmpeg` (Windows).  
Si `derush` n'est pas trouvé : ajouter au PATH (`$HOME/.local/bin` sur macOS/Linux ; redémarrer le terminal sur Windows).

## Quick Start

```bash
derush ma_video.mp4
```

Le fichier généré (FCPXML par défaut) est créé **à côté de la vidéo** (même dossier, même nom avec extension `.fcpxml`). Il s’importe dans DaVinci Resolve, FCP ou Premiere. Détail env. et commandes dev : **[PYTHON.md](PYTHON.md)**.

## Prérequis

- **FFmpeg** (obligatoire, à installer à part). Aucun Python requis.

## Dépannage

**Warning torchcodec / Pyannote** : Au lancement, vous pouvez voir un long avertissement du type « torchcodec is not installed correctly so built-in audio decoding will fail ». Il vient de Pyannote (détection de voix utilisée par WhisperX). L’audio est en réalité chargé via FFmpeg, donc le logiciel fonctionne ; le message indique toutefois un environnement à corriger.

Pour faire disparaître l’avertissement (recommandé) :
- **Option A** : Aligner les versions PyTorch / TorchCodec / FFmpeg selon la [table de compatibilité TorchCodec](https://github.com/pytorch/torchcodec?tab=readme-ov-file#installing-torchcodec), ou installer une version de FFmpeg compatible (ex. `brew install ffmpeg` et vérifier que les libs sont bien trouvées).
- **Option B** : Utiliser le VAD Silero : `derush video.mp4 --vad silero` (ou `vad_method="silero"` via l’API Python).

## Utilisation

```bash
# Analyse basique (format FCPXML par defaut)
derush video.mp4

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

# Apercu sans generer de fichier (dry-run)
derush video.mp4 --preview

# Logs detailles (decisions de coupe)
derush video.mp4 --verbose
```

## Options

| Option | Description | Defaut |
|--------|-------------|--------|
| `--output`, `-o` | Fichier de sortie | À côté de la vidéo (même nom, .fcpxml ou .json) |
| `--format`, `-f` | Format de sortie (`fcpxml`, `json`) | `fcpxml` |
| `--lang`, `-l` | Langue (`fr`, `en`). Si non spécifié : auto-détection, fallback fillers = en | auto |
| `--min-silence` | Duree min. silence à couper (secondes) | `0.5` |
| `--min-gap` | Duree min. entre mots pour couper un gap (secondes) | `0.3` |
| `--fillers` | Filler words personnalises (virgule) | liste par langue |
| `--preview` | Afficher le résumé sans générer de fichier | - |
| `--verbose`, `-v` | Afficher les décisions de coupe (mots, segments) | - |
| `--fps` | Forcer le FPS | auto (sinon 25) |
| `--model`, `-m` | Modele Whisper (`tiny`, `base`, `small`, `medium`, `large`) | `base` |
| `--vad` | VAD : `pyannote` ou `silero` (silero évite le warning torchcodec) | `pyannote` |
| `--chunk-size` | Taille max des segments VAD (secondes) ; plus petit = plus de segments | `15` |
| `--device` | Appareil (`cpu`, `cuda`) | `cpu` |
| `--version`, `-V` | Afficher la version et quitter | - |

## Formats de sortie

### FCPXML 1.9
Compatible DaVinci Resolve, Final Cut Pro. Metadonnees riches avec types silence/filler.

### JSON
Pour debug ou integrations personnalisees.

## Workflow

1. Enregistrez votre video brute
2. Lancez `derush video.mp4`
3. Importez le fichier genere dans votre logiciel de montage
4. Supprimez les segments detectes sur votre timeline

## Filler words (par défaut)

Liste définie dans `derush.config.DEFAULT_FILLERS` selon la langue :

**Français** (`--lang fr`) : euh, ben, bah, hmm, bon ben (et variantes)

**Anglais** (`--lang en` ou non spécifié) : um, uh, hmm (et variantes)

Pour en ajouter (ex. « du coup », « tu vois », « like ») : `--fillers "du coup,tu vois"`.

## Tests

```bash
make test
# ou avec couverture
./venv/bin/pytest tests/ -v --cov=derush --cov-report=html
```

## Licence

MIT License - voir [LICENSE](LICENSE)

---

Cree pour les createurs de contenu qui veulent passer moins de temps a derusher.
