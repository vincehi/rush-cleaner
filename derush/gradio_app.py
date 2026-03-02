"""Gradio web UI for derush - local interface to run the pipeline from the browser."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from derush.config import CutterConfig
from derush.cutter import run_pipeline
from derush.exceptions import DerushError, ExportError, MediaInfoError, TranscriptionError
from derush.exporters import JSONExporter, get_fcpxml_exporter
from derush.media_info import get_media_info
from derush.transcriber import transcribe

logger = logging.getLogger(__name__)


def run_derush_pipeline(
    input_path: str | None,
    output_format: str,
    language: str | None,
    min_silence: float,
    min_gap: float,
    cut_padding: float,
    model: str,
    device: str,
    progress=None,
) -> tuple[str | None, str]:
    """
    Run the full derush pipeline (media info → transcribe → cut → export).

    Returns:
        (path to output file for download, summary text). Output path is None on error.
    """
    if not input_path or not Path(input_path).exists():
        return None, "❌ Please select an audio or video file."

    input_file = Path(input_path)
    progress and progress(0.05, desc="Analyzing media...")

    try:
        media_info = get_media_info(input_file, fallback_fps=25.0)
    except MediaInfoError as e:
        return None, f"❌ Media error: {e}"

    progress and progress(0.15, desc="Transcribing (WhisperX)...")
    output_dir = input_file.parent
    whisperx_output = output_dir / f"{input_file.stem}_whisperx.json"
    lang_detect = None if language in (None, "", "None", "auto") else str(language)

    try:
        segments = transcribe(
            file_path=input_file,
            language=lang_detect,
            model_size=model,
            device=device,
            chunk_size=15,
            whisperx_output=whisperx_output,
            vad_method="pyannote",
        )
    except (TranscriptionError, DerushError, RuntimeError) as e:
        return None, f"❌ Transcription failed: {e}"

    progress and progress(0.55, desc="Detecting silences and fillers...")
    config = CutterConfig(
        min_silence=min_silence,
        min_gap_cut=min_gap,
        gap_after_filler=True,
        cut_padding=cut_padding,
    )
    lang = "en" if language in (None, "", "None", "auto") else str(language)
    result = run_pipeline(
        whisperx_path=whisperx_output,
        total_duration=media_info.duration,
        language=lang,
        custom_fillers=None,
        config=config,
    )

    progress and progress(0.85, desc="Exporting...")
    ext = ".fcpxml" if output_format == "fcpxml" else ".json"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        out_path = Path(f.name)

    exporters = {"fcpxml": get_fcpxml_exporter(), "json": JSONExporter()}
    try:
        exporters[output_format].export(
            result=result, media_info=media_info, output_path=out_path
        )
    except ExportError as e:
        return None, f"❌ Export failed: {e}"

    progress and progress(1.0, desc="Done")
    summary = (
        f"**Summary**\n"
        f"- Words: {result.total_words} ({result.filler_words} fillers)\n"
        f"- Cuts: {len(result.cuts)}\n"
        f"- Duration: {result.original_duration:.1f}s → {result.final_duration:.1f}s\n"
        f"- Reduction: {result.cut_percentage:.1f}%\n"
    )
    if result.padding_stats and cut_padding > 0:
        stats = result.padding_stats
        summary += f"- Padding: {stats.padded_count} cuts softened"
        if stats.unchanged_count > 0:
            summary += f", {stats.unchanged_count} too short (unchanged)"
        summary += "\n"
    summary += f"\nExported file: `{out_path.name}` — download below."
    return str(out_path), summary


def create_app():
    """Build and return the Gradio Blocks app."""
    try:
        import gradio as gr
    except ImportError:
        raise ImportError(
            "Gradio is not installed. Install with: pip install derush[ui]"
        ) from None

    with gr.Blocks(
        title="Derush – Video Derushing",
        theme=gr.themes.Soft(
            primary_hue="slate",
            secondary_hue="blue",
        ),
        css="""
        .summary-box { font-size: 0.95em; padding: 1em; border-radius: 8px; }
        """,
    ) as app:
        gr.Markdown("# 🎬 Derush – Automatic Derushing")
        gr.Markdown(
            "Upload a video or audio file: detect silences and filler words (um, uh...), "
            "export to FCPXML or JSON for DaVinci Resolve / Final Cut Pro."
        )

        with gr.Row():
            with gr.Column(scale=1):
                inp_file = gr.File(
                    label="Audio or video file",
                    file_types=[".mp4", ".mov", ".mkv", ".wav", ".mp3", ".m4a"],
                    type="filepath",
                )
                with gr.Accordion("Cut options", open=False):
                    min_silence = gr.Slider(
                        0.2, 5.0, value=0.5, step=0.1,
                        label="Min silence to cut (s)",
                    )
                    min_gap = gr.Slider(
                        0.1, 2.0, value=0.3, step=0.1,
                        label="Min gap between words to cut (s)",
                    )
                    cut_padding = gr.Slider(
                        0.0, 0.5, value=0.0, step=0.05,
                        label="Padding on each side of cuts (s)",
                    )
                with gr.Accordion("Transcription", open=False):
                    language = gr.Dropdown(
                        choices=["auto", "fr", "en"],
                        value="auto",
                        label="Language (auto = automatic detection)",
                    )
                    model = gr.Dropdown(
                        choices=["tiny", "base", "small", "medium", "large"],
                        value="base",
                        label="Whisper model",
                    )
                    device = gr.Radio(
                        choices=["cpu", "cuda"],
                        value="cpu",
                        label="Device",
                    )
                output_format = gr.Radio(
                    choices=["fcpxml", "json"],
                    value="fcpxml",
                    label="Export format",
                )
                run_btn = gr.Button("Run analysis", variant="primary")

            with gr.Column(scale=1):
                out_file = gr.File(label="Exported file (download)")
                out_summary = gr.Markdown(label="Summary")

        run_btn.click(
            fn=run_derush_pipeline,
            inputs=[
                inp_file,
                output_format,
                language,
                min_silence,
                min_gap,
                cut_padding,
                model,
                device,
                gr.Progress(),
            ],
            outputs=[out_file, out_summary],
        )

    return app


def launch_ui(share: bool = False, server_port: int | None = None) -> None:
    """Launch the Gradio UI (blocking)."""
    app = create_app()
    app.launch(share=share, server_port=server_port)
