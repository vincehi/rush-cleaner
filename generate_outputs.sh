#!/bin/bash
# Generate outputs from a media file using derush tool
# Usage: ./generate_outputs.sh <input_file> [language]
#
# This script does everything:
# 1. Transcribes with WhisperX
# 2. Runs cutting pipeline
# 3. Exports to FCPXML, EDL, JSON
#

set -e

# Default values
INPUT_FILE="${1:-tests/fixtures/sample.mov}"
LANGUAGE="${2:-fr}"
OUTPUT_DIR="output"
MODEL_SIZE="${3:-base}"  # tiny, base, small, medium, large-v2, large-v3

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Derush Output Generator            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""
echo "Input:    $INPUT_FILE"
echo "Language: $LANGUAGE"
echo "Model:    $MODEL_SIZE"
echo ""

# Activate virtual environment
source venv/bin/activate

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Get base filename without extension
BASENAME=$(basename "$INPUT_FILE" | sed 's/\.[^.]*$//')
WHISPERX_FILE="$OUTPUT_DIR/${BASENAME}_whisperx.json"

# Clean existing outputs for this file
echo -e "${YELLOW}Cleaning existing outputs for $BASENAME...${NC}"
rm -f "$OUTPUT_DIR/${BASENAME}".* 2>/dev/null || true
rm -rf "$OUTPUT_DIR/${BASENAME}" 2>/dev/null || true

echo -e "${BLUE}Step 1: Transcribing with WhisperX...${NC}"
python -c "
import json
import whisperx
from pathlib import Path

file_path = r'$INPUT_FILE'
language = r'$LANGUAGE'
model_size = r'$MODEL_SIZE'
output_file = Path(r'$WHISPERX_FILE')
device = 'cpu'
compute_type = 'int8'

# ASR options to improve filler detection
asr_options = {
    'hotwords': 'hmm euh um uh ben bah du coup en fait bon tu vois like you know',
    'no_speech_threshold': 0.5,
}
vad_options = {'chunk_size': 15}

print(f'Loading WhisperX model ({model_size})...')
model = whisperx.load_model(model_size, device=device, compute_type=compute_type, asr_options=asr_options, vad_options=vad_options)

print('Loading audio...')
audio = whisperx.load_audio(file_path)

print('Transcribing...')
result = model.transcribe(audio, language=language, chunk_size=15)

detected_language = result.get('language', language)

print(f'Aligning (language: {detected_language})...')
model_a, metadata = whisperx.load_align_model(language_code=detected_language, device=device)
result = whisperx.align(result['segments'], model_a, metadata, audio, device, return_char_alignments=False)

result['language'] = detected_language

# Save
output_file.parent.mkdir(parents=True, exist_ok=True)
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f'Saved: {output_file}')
print(f'Segments: {len(result.get(\"segments\", []))}')
print(f'Words: {len(result.get(\"word_segments\", []))}')
"

echo ""
echo -e "${BLUE}Step 2: Getting media info...${NC}"
python -c "
from pathlib import Path
from derush.media_info import get_media_info

media_info = get_media_info(Path(r'$INPUT_FILE'))
print(f'Duration:   {media_info.duration:.2f}s')
print(f'FPS:        {media_info.fps:.2f} ({media_info.fps_rational})')
print(f'Resolution: {media_info.width}x{media_info.height}')
"

echo ""
echo -e "${BLUE}Step 3: Running cutting pipeline and exporting...${NC}"
python -c "
from pathlib import Path
from derush.cutter import run_pipeline
from derush.config import CutterConfig
from derush.exporters import get_fcpxml_exporter, get_edl_exporter
from derush.exporters.json import JSONExporter
from derush.media_info import get_media_info

config = CutterConfig()

# Get media info
media_info = get_media_info(Path(r'$INPUT_FILE'))

# Run pipeline
result = run_pipeline(
    whisperx_path=Path(r'$WHISPERX_FILE'),
    total_duration=media_info.duration,
    language=r'$LANGUAGE',
    config=config,
)

# Export all formats
fcpxml_exporter = get_fcpxml_exporter()
fcpxml_exporter.export(result, media_info, Path(r'$OUTPUT_DIR/${BASENAME}.fcpxml'))

edl_exporter = get_edl_exporter()
edl_exporter.export(result, media_info, Path(r'$OUTPUT_DIR/${BASENAME}.edl'))

json_exporter = JSONExporter()
json_exporter.export(result, media_info, Path(r'$OUTPUT_DIR/${BASENAME}.json'))

# Summary
print()
print('═════════════════════════════════════════')
print('WORDS')
print('═════════════════════════════════════════')
for w in result.words:
    status = 'FILLER' if w.status.value == 'filler' else 'KEPT'
    print(f'  {w.word}: {w.start:.3f} -> {w.end:.3f} [{status}]')

print()
print('═══════════════════════════════════════════')
print('CUTS')
print('═════════════════════════════════════════')
for c in result.cuts:
    word_info = f' ({c.word})' if c.word else ''
    print(f'  [{c.start:.3f} -> {c.end:.3f}] {c.cut_type.value}: {c.reason.value}{word_info}')

print()
print('═══════════════════════════════════════════')
print('KEEP SEGMENTS')
print('═══════════════════════════════════════════')
for i, s in enumerate(result.keep_segments, 1):
    print(f'  {i}. [{s.start:.3f} -> {s.end:.3f}] ({s.duration:.3f}s)')

print()
print('═══════════════════════════════════════════')
print('SUMMARY')
print('═══════════════════════════════════════════')
print(f'  Original: {result.original_duration:.1f}s')
print(f'  Final:    {result.final_duration:.1f}s')
print(f'  Cut:      {result.cut_duration:.1f}s ({result.cut_percentage:.1f}%)')
print(f'  Words:    {result.total_words} total ({result.kept_words} kept, {result.filler_words} fillers)')
"

echo ""
echo -e "${GREEN}═════════════════════════════════════════${NC}"
echo -e "${GREEN}Done!${NC}"
echo -e "${GREEN}═════════════════════════════════════════${NC}"
echo ""
echo "Outputs in $OUTPUT_DIR/:"
ls -la "$OUTPUT_DIR/${BASENAME}."*
