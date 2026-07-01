from __future__ import annotations

import shutil
import tempfile
import time
import inspect
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from caye_watermark._logo import CUSTOM_LOGO_CHOICE, LOGO_CHOICES, find_default_logo, resolve_preset_logo
from caye_watermark.pipeline import (
    RESTORATION_PROFILES,
    TEMPLATES,
    ManualExif,
    ProcessingOptions,
    array_to_image,
    get_restoration_settings,
    load_image,
    process_image,
)

if TYPE_CHECKING:
    import gradio as gr

EXPORT_RETENTION_SECONDS = 24 * 60 * 60

APP_CSS = """
:root {
    --caye-bg: #f6f7f9;
    --caye-panel: #ffffff;
    --caye-border: #d8dee8;
    --caye-text: #182230;
    --caye-muted: #64748b;
    --caye-accent: #0f766e;
    --caye-accent-dark: #0b5f59;
    --caye-soft: #eef6f4;
}

.gradio-container {
    max-width: 1440px !important;
    margin: 0 auto !important;
    background: var(--caye-bg) !important;
    color: var(--caye-text) !important;
}

.caye-header {
    padding: 18px 4px 10px 4px;
}

.caye-header h1 {
    margin: 0 !important;
    font-size: 28px !important;
    line-height: 1.2 !important;
    font-weight: 700 !important;
    color: var(--caye-text) !important;
    letter-spacing: 0 !important;
}

.caye-panel {
    border: 1px solid var(--caye-border) !important;
    border-radius: 8px !important;
    background: var(--caye-panel) !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06) !important;
    padding: 16px !important;
}

.caye-panel h3 {
    margin: 0 0 12px 0 !important;
    font-size: 16px !important;
    line-height: 1.35 !important;
    font-weight: 700 !important;
    color: var(--caye-text) !important;
    letter-spacing: 0 !important;
}

.caye-stack {
    gap: 16px !important;
}

.caye-upload button,
.caye-action-row button {
    border-radius: 8px !important;
    font-weight: 700 !important;
}

.caye-upload button {
    min-height: 46px !important;
    background: var(--caye-accent) !important;
    border-color: var(--caye-accent) !important;
}

.caye-upload button:hover {
    background: var(--caye-accent-dark) !important;
    border-color: var(--caye-accent-dark) !important;
}

.caye-dropzone {
    min-height: 154px !important;
}

.caye-dropzone > label,
.caye-dropzone .wrap {
    border-radius: 8px !important;
    border-color: var(--caye-border) !important;
    background: #fbfcfd !important;
}

.caye-dng-preview .image-container,
.caye-output-preview .image-container {
    border-radius: 8px !important;
    border: 1px solid var(--caye-border) !important;
    background: #101820 !important;
}

.caye-dng-preview img,
.caye-output-preview img {
    border-radius: 6px !important;
}

.caye-form-row {
    gap: 12px !important;
}

.caye-action-row {
    margin-top: 4px !important;
}

.caye-action-row button {
    min-height: 44px !important;
}

.caye-status textarea {
    font-family: Consolas, "Microsoft YaHei UI", monospace !important;
    font-size: 13px !important;
    line-height: 1.5 !important;
    background: #fbfcfd !important;
}

.caye-download {
    min-height: 92px !important;
}

.caye-main-grid,
.caye-input-grid {
    align-items: stretch !important;
}

label span {
    color: var(--caye-muted) !important;
    font-weight: 600 !important;
}

@media (max-width: 900px) {
    .gradio-container {
        padding-left: 12px !important;
        padding-right: 12px !important;
    }

    .caye-header h1 {
        font-size: 24px !important;
    }

    .caye-panel {
        padding: 14px !important;
    }
}
"""


def import_gradio():
    try:
        import gradio as gr
    except ImportError as exc:
        raise RuntimeError(
            "gradio is required to launch the Web UI. Install project dependencies "
            "with `pip install -e .` before starting caye-watermark-web."
        ) from exc
    return gr


def supports_parameter(callable_obj, parameter_name: str) -> bool:
    try:
        return parameter_name in inspect.signature(callable_obj).parameters
    except (TypeError, ValueError):
        return False


def build_options(
    template: str,
    logo_choice: str | None,
    custom_logo_path: str | None,
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
    if not no_watermark and logo_choice and logo_choice != CUSTOM_LOGO_CHOICE:
        resolved_logo = resolve_preset_logo(logo_choice)
    elif custom_logo_path:
        p = Path(custom_logo_path)
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
        return "错误：启用水印时必须提供 Logo。请选择预设 Logo、上传自定义 Logo，或关闭水印。"
    if not 0.0 < options.watermark_scale <= 1.0:
        return "错误：水印尺寸比例必须大于 0 且不超过 1.0。"
    if not 0 <= options.opacity <= 255:
        return "错误：水印不透明度必须在 0 到 255 之间。"
    return None


def _validate_dng_file(dng_file) -> Path | str:
    if dng_file is None:
        return "请先选择一个 DNG 文件。"

    input_path = Path(dng_file).expanduser()
    if input_path.suffix.lower() != ".dng":
        return "错误：目前仅支持 .DNG 输入文件。"
    if not input_path.is_file():
        return f"错误：输入文件不存在：{input_path}"
    return input_path


def render_dng_input(input_file):
    input_path_or_error = _validate_dng_file(input_file)
    if isinstance(input_path_or_error, str):
        return None, None, input_path_or_error

    try:
        settings = get_restoration_settings("balanced")
        image = array_to_image(load_image(input_path_or_error, settings)).convert("RGB")
        image.thumbnail((900, 700), Image.Resampling.LANCZOS)
        return str(input_path_or_error), image.copy(), f"已读取 DNG：{input_path_or_error.name}"
    except Exception as exc:
        return None, None, f"错误：DNG 预览读取失败：{exc}"


def cleanup_old_exports(now: float | None = None, temp_root: Path | None = None) -> None:
    cutoff = (time.time() if now is None else now) - EXPORT_RETENTION_SECONDS
    temp_root = Path(tempfile.gettempdir()) if temp_root is None else temp_root
    for export_dir in temp_root.glob("caye_export_*"):
        try:
            if export_dir.is_dir() and export_dir.stat().st_mtime < cutoff:
                shutil.rmtree(export_dir, ignore_errors=True)
        except OSError:
            continue


def run_preview(
    input_file,
    template,
    logo_choice,
    custom_logo,
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
    input_path_or_error = _validate_dng_file(input_file)
    if isinstance(input_path_or_error, str):
        return None, input_path_or_error

    input_path = input_path_or_error
    options = build_options(
        template, logo_choice, custom_logo, upscale_factor, restoration_profile,
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

    try:
        with tempfile.TemporaryDirectory(prefix="caye_preview_") as tmpdir:
            output_path = Path(tmpdir) / "preview.png"
            process_image(input_path, output_path, options, reporter=reporter)
            with Image.open(output_path) as handle:
                preview_img = handle.copy()
            status = "\n".join(messages)
            return preview_img, status
    except Exception as exc:
        return None, f"错误：{exc}"


def run_export(
    input_file,
    template,
    logo_choice,
    custom_logo,
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
    input_path_or_error = _validate_dng_file(input_file)
    if isinstance(input_path_or_error, str):
        return None, input_path_or_error

    input_path = input_path_or_error
    options = build_options(
        template, logo_choice, custom_logo, upscale_factor, restoration_profile,
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

    cleanup_old_exports()
    output_dir = Path(tempfile.mkdtemp(prefix="caye_export_"))
    output_path = output_dir / "export.png"

    try:
        process_image(input_path, output_path, options, reporter=reporter)
        status = "\n".join(messages)
        return str(output_path), status
    except Exception as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        return None, f"错误：{exc}"


def create_ui() -> gr.Blocks:
    gr = import_gradio()
    blocks_kwargs = {
        "title": "CAYE 水印工具",
        "fill_width": True,
    }
    if supports_parameter(gr.Blocks, "css"):
        blocks_kwargs["css"] = APP_CSS

    with gr.Blocks(**blocks_kwargs) as app:
        gr.Markdown("# CAYE 水印工具", elem_classes=["caye-header"])

        current_input = gr.State(None)

        with gr.Row(elem_classes=["caye-main-grid"]):
            with gr.Column(scale=5, min_width=360, elem_classes=["caye-stack"]):
                with gr.Group(elem_classes=["caye-panel"]):
                    gr.Markdown("### 输入")
                    with gr.Row(elem_classes=["caye-input-grid"]):
                        with gr.Column(scale=3, min_width=260):
                            upload_button = gr.UploadButton(
                                label="选择 DNG 文件",
                                file_count="single",
                                file_types=[".dng"],
                                type="filepath",
                                variant="primary",
                                size="lg",
                                elem_classes=["caye-upload"],
                            )
                            input_file = gr.File(
                                label="拖入 DNG 文件",
                                file_count="single",
                                file_types=[".dng"],
                                type="filepath",
                                height=150,
                                interactive=True,
                                elem_classes=["caye-dropzone"],
                            )
                        with gr.Column(scale=4, min_width=300):
                            input_render = gr.Image(
                                label="DNG 读取预览",
                                type="pil",
                                height=300,
                                interactive=False,
                                elem_classes=["caye-dng-preview"],
                            )
                    with gr.Row(elem_classes=["caye-form-row"]):
                        template = gr.Dropdown(
                            choices=list(TEMPLATES),
                            value="standard-footer",
                            label="水印模板",
                        )
                        logo_choice = gr.Dropdown(
                            choices=list(LOGO_CHOICES),
                            value="CAYE.webp",
                            label="Logo 图片",
                        )
                        logo_upload = gr.File(
                            label="自定义 Logo 图片",
                            file_types=[".png", ".webp", ".jpg", ".jpeg"],
                            type="filepath",
                            visible=False,
                        )

                with gr.Group(elem_classes=["caye-panel"]):
                    gr.Markdown("### EXIF 信息")
                    with gr.Row(elem_classes=["caye-form-row"]):
                        camera_model = gr.Textbox(label="相机型号", placeholder="例如：Canon EOS R5")
                        lens_model = gr.Textbox(label="镜头型号", placeholder="例如：RF 50mm f/1.2L")
                    with gr.Row(elem_classes=["caye-form-row"]):
                        focal_length_35mm = gr.Textbox(label="焦距", placeholder="例如：50mm")
                        captured_at = gr.Textbox(label="拍摄日期", placeholder="例如：2024-06-15")
                    with gr.Row(elem_classes=["caye-form-row"]):
                        aperture = gr.Textbox(label="光圈", placeholder="例如：2.8")
                        shutter_speed = gr.Textbox(label="快门速度", placeholder="例如：1/125")
                        iso = gr.Textbox(label="ISO", placeholder="例如：400")

                with gr.Group(elem_classes=["caye-panel"]):
                    gr.Markdown("### 处理参数")
                    with gr.Row(elem_classes=["caye-form-row"]):
                        upscale_factor = gr.Slider(
                            minimum=1, maximum=4, step=1, value=4,
                            label="放大倍数",
                        )
                        restoration_profile = gr.Dropdown(
                            choices=list(RESTORATION_PROFILES),
                            value="balanced",
                            label="修复模式",
                        )
                    with gr.Row(elem_classes=["caye-form-row"]):
                        watermark_scale = gr.Slider(
                            minimum=0.05, maximum=0.5, step=0.01, value=0.22,
                            label="水印尺寸",
                        )
                        opacity = gr.Slider(
                            minimum=0, maximum=255, step=1, value=235,
                            label="水印不透明度",
                        )
                    no_watermark = gr.Checkbox(label="不添加水印", value=False)
                    with gr.Row(elem_classes=["caye-action-row"]):
                        preview_btn = gr.Button("生成预览", variant="secondary")
                        export_btn = gr.Button("导出 PNG", variant="primary")

            with gr.Column(scale=4, min_width=360, elem_classes=["caye-stack"]):
                with gr.Group(elem_classes=["caye-panel"]):
                    gr.Markdown("### 输出")
                    preview_image = gr.Image(
                        label="处理预览",
                        type="pil",
                        height=520,
                        elem_classes=["caye-output-preview"],
                    )
                with gr.Group(elem_classes=["caye-panel"]):
                    status_text = gr.Textbox(
                        label="状态",
                        lines=8,
                        interactive=False,
                        elem_classes=["caye-status"],
                    )
                    export_file = gr.File(
                        label="下载导出文件",
                        visible=True,
                        elem_classes=["caye-download"],
                    )

        def toggle_custom_logo(choice: str):
            return gr.update(visible=choice == CUSTOM_LOGO_CHOICE)

        logo_choice.change(
            fn=toggle_custom_logo,
            inputs=[logo_choice],
            outputs=[logo_upload],
        )

        upload_button.upload(
            fn=render_dng_input,
            inputs=[upload_button],
            outputs=[current_input, input_render, status_text],
        )

        input_file.change(
            fn=render_dng_input,
            inputs=[input_file],
            outputs=[current_input, input_render, status_text],
        )

        preview_inputs = [
            current_input, template, logo_choice, logo_upload, upscale_factor,
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
    gr = import_gradio()
    app = create_ui()
    launch_kwargs = {
        "server_name": "127.0.0.1",
        "server_port": None,
        "theme": gr.themes.Soft(),
        "inbrowser": True,
    }
    if supports_parameter(app.launch, "css"):
        launch_kwargs["css"] = APP_CSS
    app.launch(**launch_kwargs)


if __name__ == "__main__":
    launch_app()
