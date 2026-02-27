# Derush MVP

**Outil de dérushage vidéo automatique** - Détectez les silences et les hésitations pour accélérer votre montage vidéo de 50%+.

## Qu'est-ce que c'est ?

Derush MVP est un outil en ligne de commande qui analyse vos vidéos brutes et génère automatiquement un fichier de coupe (cuts) importable dans votre logiciel de montage vidéo préféré (DaVinci Resolve, Final Cut Pro, Adobe Premiere Pro).

L'outil détecte automatiquement :
- **Les silences** - Gaps audio entre les segments parlés
- **Les hésitations** - Filler words comme "euh", "um", "ben", "du coup", etc.

## Installation

### Prérequis

1. **Python 3.10 à 3.13** (⚠️ Python 3.14 non supporté par WhisperX)
   ```bash
   python --version  # Doit afficher 3.10, 3.11, 3.12 ou 3.13
   ```

   Si vous avez Python 3.14, installez Python 3.12 via pyenv :
   ```bash
   brew install pyenv
   pyenv install 3.12
   cd derush-mvp
   pyenv local 3.12
   ```

2. **FFmpeg** (nécessaire pour l'analyse vidéo)
   - **macOS** : `brew install ffmpeg`
   - **Ubuntu/Debian** : `sudo apt install ffmpeg`
   - **Windows** : Télécharger depuis [ffmpeg.org](https://ffmpeg.org/download.html)

### Installation de l'outil

```bash
# Cloner ou télécharger le projet
cd derush-mvp

# Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -e ".[dev]"
```

### Vérification de l'installation

```bash
# Vérifier que ffprobe est disponible
ffprobe -version

# Vérifier que derush est installé
derush --help
```

## Utilisation

### Utilisation basique

```bash
# Analyser une vidéo et générer un fichier FCPXML (par défaut)
derush ma_video.mp4

# Spécifier le format de sortie
derush ma_video.mp4 --format edl

# Spécifier la langue (fr ou en)
derush ma_video.mp4 --lang fr

# Spécifier un fichier de sortie personnalisé
derush ma_video.mp4 --output mes_cuts.fcpxml
```

### Options disponibles

| Option | Description | Valeur par défaut |
|--------|-------------|-------------------|
| `--format`, `-f` | Format de sortie (`fcpxml`, `edl`, `json`) | `fcpxml` |
| `--lang`, `-l` | Langue (`fr`, `en`, ou auto-détection) | auto |
| `--min-silence` | Durée minimale de silence à détecter (secondes) | `0.5` |
| `--fillers` | Liste personnalisée de filler words (séparés par des virgules) | - |
| `--fps` | Forcer le FPS (auto-détecté par défaut) | auto |
| `--model`, `-m` | Taille du modèle Whisper (`tiny`, `base`, `small`, `medium`, `large`) | `base` |
| `--device` | Appareil pour la transcription (`cpu` ou `cuda`) | `cpu` |
| `--output`, `-o` | Fichier de sortie personnalisé | basé sur l'entrée |

### Exemples avancés

```bash
# Détecter les silences de plus de 0.3 secondes
derush video.mp4 --min-silence 0.3

# Ajouter des filler words personnalisés
derush video.mp4 --fillers "en fait,du coup,tu vois"

# Utiliser un modèle plus précis (plus lent)
derush video.mp4 --model large

# Utiliser le GPU pour accélérer la transcription
derush video.mp4 --device cuda

# Export JSON pour analyse/debug
derush video.mp4 --format json --output analyse.json
```

## Formats de sortie

### FCPXML 1.9
- **Compatible avec** : DaVinci Resolve, Final Cut Pro
- **Avantages** : Métadonnées riches (type silence/filler), supporte les timecodes rationnels
- **Extension** : `.fcpxml`

### EDL (CMX3600)
- **Compatible avec** : DaVinci Resolve, Adobe Premiere Pro, Avid Media Composer
- **Avantages** : Compatibilité maximale, standard de l'industrie
- **Extension** : `.edl`

### JSON
- **Usage** : Débogage, intégration personnalisée
- **Avantages** : Facilement parsable, inclut un résumé des détections
- **Extension** : `.json`

## Workflow typique

1. **Enregistrez votre vidéo** brute (non montée)

2. **Lancez derush** :
   ```bash
   derush ma_video.mp4 --format fcpxml --lang fr
   ```

3. **Importez le fichier généré** dans votre logiciel de montage :
   - DaVinci Resolve : File → Import → Timeline
   - Final Cut Pro : File → Import → XML
   - Premiere Pro : Utiliser EDL format

4. **Supprimez rapidement** les segments détectés sur votre timeline

5. **Gagnez du temps** sur le dérushage !

## Comprendre les résultats

### Exemple de sortie console

```
Analyzing media file: ma_video.mp4
  FPS: 25.0 (25/1)
  Duration: 120.0s
  Resolution: 1920x1080

Transcribing audio...
  Found 45 segments

Detecting silences...
  Found 12 silences

Detecting filler words (language: fr)...
  Found 8 filler words

Exporting to FCPXML...

Summary:
  Total cuts: 20
  - Silences: 12
  - Fillers: 8
  Total cut duration: 35.2s

Output saved to: ma_video.fcpxml
```

### Filler words détectés par défaut

**Français** : euh, ben, du coup, en fait, bon, bah, quoi, tu vois

**Anglais** : um, uh, like, you know, I mean, basically, so, right

## Tests

```bash
# Lancer tous les tests
pytest tests/ -v

# Lancer avec couverture de code
pytest tests/ --cov=src --cov-report=html

# Lancer uniquement les tests rapides (sans intégration)
pytest tests/ -v -m "not integration"
```

## Structure du projet

```
derush-mvp/
├── src/
│   ├── cli.py              # Interface en ligne de commande
│   ├── transcriber.py      # Transcription WhisperX
│   ├── silence_detector.py # Détection des silences
│   ├── filler_detector.py  # Détection des filler words
│   ├── media_info.py       # Extraction métadonnées (FPS, durée)
│   ├── models.py           # Modèles de données
│   └── exporters/          # Exportateurs (FCPXML, EDL, JSON)
├── tests/                  # Tests unitaires et d'intégration
├── pyproject.toml          # Configuration du projet
└── README.md               # Ce fichier
```

## Dépannage

### "ffprobe not found"
Installez FFmpeg (voir section Prérequis).

### "whisperx is not installed"
Installez les dépendances : `pip install -e ".[dev]"`

### La transcription est lente
- Utilisez un modèle plus petit : `--model tiny`
- Utilisez le GPU si disponible : `--device cuda`

### Les timecodes sont décalés
- Vérifiez que le FPS détecté est correct (affiché au début)
- Forcez le FPS si nécessaire : `--fps 25`

## Licence

MIT License

## Contribution

Les contributions sont les bienvenues ! Ouvrez une issue ou soumettez une pull request.

---

**Créé pour les créateurs de contenu qui veulent passer moins de temps à dérusher et plus de temps à créer.**
