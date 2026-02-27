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
