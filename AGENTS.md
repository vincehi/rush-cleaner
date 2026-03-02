# Derush - AI Context

Outil de dérushage vidéo automatique. Détecte les silences et filler words, génère des fichiers de coupe (FCPXML, EDL, JSON) pour DaVinci Resolve, Final Cut Pro, Premiere Pro.

## Architecture

```
src/
├── transcriber.py    # WhisperX transcription + word-level alignment
├── cutter.py         # Pipeline: correction timestamps → classification → cuts → keep_segments
├── exporters/        # FCPXML, EDL, JSON
├── config.py         # Filler words, seuils
└── models.py         # Dataclasses
```

## Pipeline

1. **Transcription** - WhisperX avec hotwords pour détecter les fillers
2. **Correction** - Ajuste les mots trop longs (>2s) ou mal alignés (score <0.5)
3. **Classification** - Marque les fillers (euh, hmm, ben, bah)
4. **Cuts** - Détecte silences + fillers + gaps
5. **Export** - FCPXML/EDL/JSON

## Commandes utiles

```bash
# Tester avec le sample
./generate_outputs.sh

# Tests
pytest tests/ -v

# Linter
ruff check src/
```

## Filler words actuels

- **FR**: euh, ben, bah, hmm, bon ben
- **EN**: um, uh, hmm

## Export FCPXML (DaVinci Resolve / FCP)

### Stéréo audio

Pour que le son soit bien stéréo (deux canaux) après import dans Resolve :

- **Un seul asset** par fichier source (pas deux refs r2/r4).
- **Un seul `asset-clip`** par segment dans la spine (pas de doublon par segment).
- Sur l’asset : **`audioSources="2"`** et **`audioChannels="1"`** (deux sources mono = L/R), pas `audioSources="1"` + `audioChannels="2"` (Resolve importe souvent ça en mono ou un seul côté).

### Structure pour Resolve

- Asset : enfant **`<media-rep src="..." kind="original-media"/>`** (style export DaVinci), pas uniquement l’attribut `src` sur l’asset.
- Chaque `asset-clip` : **`enabled="1"`** et enfant **`<adjust-transform scale="1 1" anchor="0 0" position="0 0"/>`** pour le positionnement.
- Séquence : **`audioLayout="stereo"`** et **`audioRate="48000"`**.

### Si le son reste d’un seul côté après import

Bug connu Resolve sur l’import FCPXML. Contournement : sélectionner les clips → Clic droit → Clip Attributes → onglet Audio → colonne Source Channel : assigner les canaux (Embedded 1, Embedded 2) au lieu de Mute.
