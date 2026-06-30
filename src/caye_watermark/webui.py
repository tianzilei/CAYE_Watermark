from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import gradio as gr
from PIL import Image

from caye_watermark._logo import find_default_logo
from caye_watermark.pipeline import (
    RESTORATION_PROFILES,
    TEMPLATES,
    ManualExif,
    ProcessingOptions,
    process_image,
)


def build_options(
    template: str,
    logo_path: str | None,
    upscale_factor: int,
    restoration_profile: str,
    watermark_scale: float,
    opacity: int,
    no_watermark: bool,
    camera_model: str,
    lens_model: str,
    focal_length_35mm: str,
    aperture: str,
    shutter_speed: str,
    iso: str,
    captured_at: str,
) -> ProcessingOptions:
    resolved_logo: Path | None = None
    if logo_path:
        p = Path(logo_path)
        if p.exists():
            resolved_logo = p
    elif not no_watermark:
        resolved_logo = find_default_logo()

    return ProcessingOptions(
        template=template,
        watermark_image=resolved_logo,
        enable_watermark=not no_watermark,
        upscale_factor=int(upscale_factor),
        restoration_profile=restoration_profile,
        watermark_scale=float(watermark_scale),
        opacity=int(opacity),
        manual_exif=ManualExif(
            camera_model=camera_model or "",
            lens_model=lens_model or "",
            focal_length_35mm=focal_length_35mm or "",
            aperture=aperture or "",
            shutter_speed=shutter_speed or "",
            iso=iso or "",
            captured_at=captured_at or "",
        ),
    )


def _validate_options(options: ProcessingOptions) -> str | None:
    if options.enable_watermark and options.watermark_image is None:
        return "Error: A logo is required when watermark is enabled. Upload a logo or disable watermark."
    return None


def run_preview(
    dng_file,
    template,
    logo,
    upscale_factor,
    restoration_profile,
    watermark_scale,
    opacity,
    no_watermark,
    camera_model,
    lens_model,
    focal_length_35mm,
    aperture,
    shutter_speed,
    iso,
    captured_at,
):
    if dng_file is None:
        return None, "Please upload a DNG file."

    input_path = Path(dng_file)
    options = build_options(
        template, logo, upscale_factor, restoration_profile,
        watermark_scale, opacity, no_watermark,
        camera_model, lens_model, focal_length_35mm,
        aperture, shutter_speed, iso, captured_at,
    )

    error = _validate_options(options)
    if error:
        return None, error

    messages: list[str] = []

    def reporter(stage: str, message: str) -> None:
        messages.append(f"[{stage}] {message}")

    output_path = Path(tempfile.mktemp(suffix=".png"))
    try:
        process_image(input_path, output_path, options, reporter=reporter)
        preview_img = Image.open(output_path)
        status = "\n".join(messages)
        return preview_img, status
    except Exception as exc:
        return None, f"Error: {exc}"
    finally:
        output_path.unlink(missing_ok=True)


def run_export(
    dng_file,
    template,
    logo,
    upscale_factor,
    restoration_profile,
    watermark_scale,
    opacity,
    no_watermark,
    camera_model,
    lens_model,
    focal_length_35mm,
    aperture,
    shutter_speed,
    iso,
    captured_at,
):
    if dng_file is None:
        return None, "Please upload a DNG file."

    input_path = Path(dng_file)
    options = build_options(
        template, logo, upscale_factor, restoration_profile,
        watermark_scale, opacity, no_watermark,
        camera_model, lens_model, focal_length_35mm,
        aperture, shutter_speed, iso, captured_at,
    )

    error = _validate_options(options)
    if error:
        return None, error

    messages: list[str] = []

    def reporter(stage: str, message: str) -> None:
        messages.append(f"[{stage}] {message}")

    output_dir = Path(tempfile.mkdtemp(prefix="caye_export_"))
    output_path = output_dir / "export.png"

    try:
        process_image(input_path, output_path, options, reporter=reporter)
        status = "\n".join(messages)
        return str(output_path), status
    except Exception as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        return None, f"Error: {exc}"


def create_ui() -> gr.Blocks:
    with gr.Blocks(title="CAYE Watermark") as app:
        gr.Markdown("# CAYE Watermark")

        with gr.Row():
            with gr.Column(scale=1):
                dng_upload = gr.File(
                    label="Upload DNG",
                    file_types=[".dng"],
                    type="filepath",
                )
                template = gr.Dropdown(
                    choices=list(TEMPLATES),
                    value="standard-footer",
                    label="Template",
                )
                logo_upload = gr.File(
                    label="Logo Image (optional, uses default if empty)",
                    file_types=[".png", ".webp", ".jpg", ".jpeg"],
                    type="filepath",
                )

                gr.Markdown("### EXIF Info")
                camera_model = gr.Textbox(label="Camera Model", placeholder="e.g. Canon EOS R5")
                lens_model = gr.Textbox(label="Lens Model", placeholder="e.g. RF 50mm f/1.2L")
                focal_length_35mm = gr.Textbox(label="Focal Length", placeholder="e.g. 50mm")
                aperture = gr.Textbox(label="Aperture", placeholder="e.g. 2.8")
                shutter_speed = gr.Textbox(label="Shutter Speed", placeholder="e.g. 1/125")
                iso = gr.Textbox(label="ISO", placeholder="e.g. 400")
                captured_at = gr.Textbox(label="Capture Date", placeholder="e.g. 2024-06-15")

                gr.Markdown("### Processing")
                upscale_factor = gr.Slider(
                    minimum=1, maximum=4, step=1, value=4,
                    label="Upscale Factor",
                )
                restoration_profile = gr.Dropdown(
                    choices=list(RESTORATION_PROFILES),
                    value="balanced",
                    label="Restoration Profile",
                )
                watermark_scale = gr.Slider(
                    minimum=0.05, maximum=0.5, step=0.01, value=0.22,
                    label="Watermark Scale",
                )
                opacity = gr.Slider(
                    minimum=0, maximum=255, step=1, value=235,
                    label="Watermark Opacity",
                )
                no_watermark = gr.Checkbox(label="Disable Watermark", value=False)

                with gr.Row():
                    preview_btn = gr.Button("Preview", variant="secondary")
                    export_btn = gr.Button("Export PNG", variant="primary")

            with gr.Column(scale=1):
                preview_image = gr.Image(label="Preview", type="pil")
                status_text = gr.Textbox(label="Status", lines=6, interactive=False)
                export_file = gr.File(label="Download Export", visible=True)

        preview_inputs = [
            dng_upload, template, logo_upload, upscale_factor,
            restoration_profile, watermark_scale, opacity, no_watermark,
            camera_model, lens_model, focal_length_35mm,
            aperture, shutter_speed, iso, captured_at,
        ]

        preview_btn.click(
            fn=run_preview,
            inputs=preview_inputs,
            outputs=[preview_image, status_text],
        )

        export_btn.click(
            fn=run_export,
            inputs=preview_inputs,
            outputs=[export_file, status_text],
        )

    return app


def launch_app() -> None:
    app = create_ui()
    app.launch(server_name="127.0.0.1", server_port=7860, theme=gr.themes.Soft())


if __name__ == "__main__":
    launch_app()
