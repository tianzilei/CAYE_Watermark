from __future__ import annotations

import shutil
import socket
import sys
import tempfile
import threading
import time
import inspect
import os
import uuid
import warnings
import webbrowser
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
EXPORT_DIR_NAME = "caye_exports"
DEFAULT_WEB_PORT = 7860
WEB_PORT_SCAN_LIMIT = 10

APP_CSS = """
@import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Noto+Sans+SC:wght@400;500;700;800&display=swap");

:root {
    --caye-bg: #f6f0e5;
    --caye-bg-strong: #fbf7f1;
    --caye-panel: rgba(255, 255, 255, 0.84);
    --caye-panel-strong: #ffffff;
    --caye-border: rgba(24, 34, 48, 0.08);
    --caye-text: #182533;
    --caye-muted: #607081;
    --caye-accent: #0f766e;
    --caye-accent-dark: #0a4f4b;
    --caye-accent-soft: #dff4ef;
    --caye-gold: #d5a43a;
    --caye-shadow: 0 24px 64px rgba(23, 34, 48, 0.09);
}

.gradio-container {
    max-width: 1480px !important;
    margin: 0 auto !important;
    background: var(--caye-bg) !important;
    color: var(--caye-text) !important;
    font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei UI", sans-serif !important;
    padding: 30px 24px 54px 24px !important;
    position: relative;
    overflow: hidden;
    background-image:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.08), transparent 28%),
        radial-gradient(circle at 84% 10%, rgba(213, 164, 58, 0.12), transparent 24%),
        linear-gradient(180deg, #fbf8f1 0%, #f3eee4 100%) !important;
}

.gradio-container::before,
.gradio-container::after {
    content: "";
    position: absolute;
    width: 340px;
    height: 340px;
    border-radius: 50%;
    pointer-events: none;
    filter: blur(18px);
    opacity: 0.7;
}

.gradio-container::before {
    top: -120px;
    right: -110px;
    background: radial-gradient(circle, rgba(15, 118, 110, 0.16) 0%, rgba(15, 118, 110, 0) 68%);
}

.gradio-container::after {
    left: -140px;
    bottom: 14%;
    background: radial-gradient(circle, rgba(213, 164, 58, 0.12) 0%, rgba(213, 164, 58, 0) 70%);
}

.gradio-container .prose,
.gradio-container .prose p,
.gradio-container .prose span,
.gradio-container .prose strong,
.gradio-container .prose h1,
.gradio-container .prose h2,
.gradio-container .prose h3 {
    color: var(--caye-text) !important;
}

.gradio-container footer {
    display: none !important;
}

.caye-panel {
    position: relative;
    overflow: hidden;
    border: 1px solid var(--caye-border) !important;
    border-radius: 28px !important;
    background: var(--caye-panel) !important;
    box-shadow: var(--caye-shadow) !important;
    padding: 26px !important;
    backdrop-filter: blur(18px) !important;
}

.caye-panel::before {
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 86px;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.36) 0%, rgba(255, 255, 255, 0) 100%);
    pointer-events: none;
}

.caye-panel > .styler {
    background: transparent !important;
    border-radius: inherit !important;
    overflow: hidden !important;
    box-shadow: none !important;
}

.caye-panel > .styler > .block {
    border-radius: inherit !important;
}

.caye-section-head {
    position: relative;
    z-index: 1;
    display: grid;
    gap: 4px;
    margin-bottom: 12px;
    padding: 0 10px;
}

.caye-section-title {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.caye-section-kicker {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: fit-content;
    padding: 4px 8px;
    border-radius: 999px;
    background: var(--caye-accent-soft);
    color: var(--caye-accent-dark);
    font-size: 10px;
    line-height: 1;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 800;
}

.caye-section-head h3 {
    margin: 0 !important;
    font-size: 18px !important;
    line-height: 1.15 !important;
    font-weight: 800 !important;
    color: var(--caye-text) !important;
    letter-spacing: -0.01em !important;
}

.caye-section-head p {
    margin: 0 !important;
    color: var(--caye-muted) !important;
    font-size: 12px !important;
    line-height: 1.5 !important;
}

.caye-stack {
    gap: 20px !important;
}

.caye-main-grid {
    align-items: flex-start !important;
    gap: 20px !important;
}

.caye-stage-column {
    position: sticky;
    top: 24px;
}

.caye-upload-shell {
    display: grid !important;
    grid-template-columns: minmax(320px, 0.95fr) minmax(0, 1.05fr);
    gap: 18px !important;
    align-items: stretch !important;
}

.caye-uploader-card,
.caye-side-preview-card {
    border-radius: 16px !important;
    border: none !important;
    background: transparent !important;
    padding: 10px !important;
    box-shadow: none !important;
}

.caye-subtitle {
    margin: 0 0 12px 0;
    font-size: 14px;
    line-height: 1.6;
    color: var(--caye-muted);
}

.caye-dropzone {
    min-height: 228px !important;
    border-radius: 20px !important;
}

.caye-dropzone [data-testid="block-label"] {
    display: none !important;
}

.caye-dropzone > label,
.caye-dropzone .wrap {
    min-height: 228px !important;
    border-radius: 20px !important;
    border: 1px dashed rgba(15, 118, 110, 0.26) !important;
    background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(242, 249, 247, 0.92) 100%) !important;
}

.caye-dropzone .or {
    color: var(--caye-muted) !important;
}

.caye-dropzone button {
    width: 100% !important;
    min-height: 228px !important;
    border-radius: 20px !important;
    padding: 18px !important;
}

.caye-dropzone button > .wrap {
    display: grid !important;
    justify-items: center !important;
    align-content: center !important;
    gap: 8px !important;
    text-align: center !important;
    line-height: 1.45 !important;
    white-space: normal !important;
}

.caye-dropzone button .icon-wrap {
    width: 32px !important;
    height: 32px !important;
    margin: 0 auto !important;
}

.caye-dropzone button .or {
    display: block !important;
    margin: 0 !important;
}

.caye-action-row button,
.caye-download button {
    border-radius: 18px !important;
    font-weight: 700 !important;
    border: 1px solid transparent !important;
    transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease, border-color 0.18s ease !important;
}

.caye-download button {
    min-height: 48px !important;
    background: linear-gradient(135deg, var(--caye-accent) 0%, #1c9f85 100%) !important;
    border-color: var(--caye-accent) !important;
    box-shadow: 0 14px 28px rgba(15, 118, 110, 0.22) !important;
    color: #ffffff !important;
}

.caye-download button:hover {
    background: var(--caye-accent-dark) !important;
    border-color: var(--caye-accent-dark) !important;
    transform: translateY(-1px) !important;
}

.caye-upload-note {
    margin: 2px 0 0 0 !important;
    color: var(--caye-muted) !important;
    font-size: 13px !important;
}

.caye-dng-preview,
.caye-output-preview {
    width: 100% !important;
}

.caye-dng-preview .image-container,
.caye-output-preview .image-container {
    border-radius: 16px !important;
    border: 1px solid rgba(21, 32, 43, 0.08) !important;
    width: 100% !important;
    max-width: 100% !important;
    overflow: hidden !important;
}

.caye-dng-preview .image-container {
    min-height: 360px !important;
    background:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.18), transparent 32%),
        linear-gradient(180deg, #13232d 0%, #172934 100%) !important;
}

.caye-output-preview .image-container {
    min-height: 640px !important;
    border: none !important;
    box-shadow:
        inset 0 0 0 1px rgba(24, 37, 51, 0.12),
        0 10px 24px rgba(24, 37, 51, 0.04) !important;
    background:
        linear-gradient(180deg, rgba(250, 252, 254, 0.94) 0%, rgba(240, 245, 250, 0.84) 100%) !important;
}

.caye-dng-preview .empty,
.caye-output-preview .empty {
    color: rgba(255, 255, 255, 0.72) !important;
}

.caye-output-preview .empty {
    color: var(--caye-muted) !important;
}

.caye-dng-preview img,
.caye-output-preview img {
    display: block !important;
    width: 100% !important;
    height: auto !important;
    max-width: 100% !important;
}

.caye-form-grid {
    gap: 12px !important;
    flex-wrap: wrap !important;
}

.caye-form-row {
    gap: 12px !important;
    flex-wrap: wrap !important;
}

.caye-form-grid > div,
.caye-form-row > div,
.caye-action-row > div {
    min-width: 0 !important;
}

.caye-date-field input {
    min-width: 0 !important;
}

.caye-fieldset {
    padding: 8px 10px 12px 10px !important;
    border-radius: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

.caye-fieldset + .caye-fieldset {
    margin-top: 10px !important;
    padding-top: 16px !important;
    border-top: 1px solid rgba(21, 32, 43, 0.08) !important;
}

.caye-subsection-title {
    margin: 0 0 12px 0 !important;
    font-size: 14px !important;
    line-height: 1.3 !important;
    font-weight: 800 !important;
    color: var(--caye-text) !important;
}

.caye-helper {
    margin: 0 !important;
    color: var(--caye-muted) !important;
    font-size: 13px !important;
    line-height: 1.6 !important;
}

.caye-helper code {
    background: rgba(21, 32, 43, 0.06);
    border-radius: 8px;
    padding: 2px 6px;
}

.caye-action-bar {
    display: grid !important;
    gap: 12px !important;
    margin-top: 8px !important;
    padding: 18px 10px 4px 10px !important;
    border-radius: 0 !important;
    background: transparent !important;
    border: none !important;
    border-top: 1px solid rgba(21, 32, 43, 0.08) !important;
    box-shadow: none !important;
}

.caye-action-row {
    display: grid !important;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px !important;
    align-items: stretch !important;
}

.caye-action-row button {
    min-height: 56px !important;
    font-size: 15px !important;
    width: 100% !important;
}

.caye-action-row .secondary {
    background: rgba(255, 255, 255, 0.96) !important;
    color: var(--caye-accent-dark) !important;
    border-color: rgba(15, 118, 110, 0.12) !important;
    box-shadow: 0 12px 26px rgba(15, 118, 110, 0.08) !important;
}

.caye-action-row .secondary:hover {
    background: rgba(255, 255, 255, 1) !important;
    transform: translateY(-1px) !important;
}

.caye-export-copy {
    display: grid !important;
    gap: 8px !important;
    align-content: start !important;
}

.caye-export-copy h3 {
    margin-bottom: 6px !important;
}

.caye-status textarea {
    font-family: "IBM Plex Mono", "Noto Sans SC", "SFMono-Regular", "Microsoft YaHei UI", monospace !important;
    font-size: 13px !important;
    line-height: 1.6 !important;
    background: rgba(248, 250, 252, 0.94) !important;
    border-radius: 18px !important;
    min-height: 180px !important;
}

.caye-status label,
.caye-output-preview label,
.caye-dng-preview label,
.caye-dropzone label {
    margin-bottom: 10px !important;
}

.caye-main-grid label > span,
.caye-panel label > span {
    color: var(--caye-muted) !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 0.01em !important;
}

.caye-panel input,
.caye-panel textarea,
.caye-panel .wrap,
.caye-panel .select-wrap,
.caye-panel .gradio-dropdown,
.caye-panel .gradio-checkbox {
    border-radius: 16px !important;
}

.caye-panel input,
.caye-panel textarea,
.caye-panel .wrap,
.caye-panel .select-wrap {
    border-color: rgba(21, 32, 43, 0.08) !important;
    background: rgba(255, 255, 255, 0.96) !important;
}

.caye-panel input:focus,
.caye-panel textarea:focus {
    border-color: rgba(15, 118, 110, 0.32) !important;
    box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.08) !important;
}

.caye-panel .block {
    overflow: visible !important;
}

.caye-status-panel {
    display: grid !important;
    gap: 12px !important;
}

.caye-preview-note {
    margin: 12px 0 0 0 !important;
    padding: 0 10px !important;
    color: var(--caye-muted) !important;
    font-size: 13px !important;
    line-height: 1.7 !important;
}

.caye-inline-path {
    padding: 0 10px !important;
}

.caye-inline-path code {
    background: rgba(21, 32, 43, 0.06);
    border-radius: 8px;
    padding: 3px 8px;
    font-size: 12px;
    white-space: pre-wrap !important;
    word-break: break-all !important;
}

@keyframes caye-rise {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.caye-panel {
    animation: caye-rise 0.48s ease both;
}

@media (max-width: 1180px) {
    .caye-upload-shell {
        grid-template-columns: 1fr !important;
    }

    .caye-form-row {
        gap: 10px !important;
    }

    .caye-stage-column {
        position: static !important;
    }
}

@media (max-width: 900px) {
    .gradio-container {
        padding: 16px 12px 32px 12px !important;
    }

    .caye-panel {
        padding: 18px !important;
        border-radius: 20px !important;
    }

    .caye-section-head,
    .caye-preview-note,
    .caye-inline-path {
        padding-left: 4px !important;
        padding-right: 4px !important;
    }

    .caye-dng-preview .image-container {
        min-height: 260px !important;
    }

    .caye-output-preview .image-container {
        min-height: 420px !important;
    }

    .caye-action-row {
        grid-template-columns: 1fr !important;
    }

    .caye-dropzone button {
        min-height: 200px !important;
        padding: 16px !important;
    }
}
"""


def import_gradio():
    warnings.filterwarnings(
        "ignore",
        message=r".*HTTP_422_UNPROCESSABLE_ENTITY.*HTTP_422_UNPROCESSABLE_CONTENT.*",
        category=_starlette_deprecation_warning(),
        module=r"gradio\.routes",
    )
    try:
        import gradio as gr
    except ImportError as exc:
        raise RuntimeError(
            "gradio is required to launch the Web UI. Install project dependencies "
            "with `pip install -e .` before starting caye-watermark-web."
        ) from exc
    return gr


def _starlette_deprecation_warning() -> type[Warning]:
    try:
        from starlette.exceptions import StarletteDeprecationWarning
    except Exception:
        return Warning
    return StarletteDeprecationWarning


def supports_parameter(callable_obj, parameter_name: str) -> bool:
    try:
        return parameter_name in inspect.signature(callable_obj).parameters
    except (TypeError, ValueError):
        return False


def find_available_port(host: str = "127.0.0.1", start_port: int = DEFAULT_WEB_PORT) -> int:
    for port in range(start_port, start_port + WEB_PORT_SCAN_LIMIT + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def open_browser_later(url: str, delay_seconds: float = 1.0) -> None:
    def _open() -> None:
        time.sleep(delay_seconds)
        try:
            webbrowser.open(url, new=2)
        except Exception:
            pass

    threading.Thread(target=_open, daemon=True).start()


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
    temp_root = get_export_root() if temp_root is None else temp_root
    for export_path in temp_root.glob("caye_export_*"):
        try:
            if export_path.stat().st_mtime >= cutoff:
                continue
            if export_path.is_dir():
                shutil.rmtree(export_path, ignore_errors=True)
            elif export_path.is_file():
                export_path.unlink(missing_ok=True)
        except OSError:
            continue


def get_export_root() -> Path:
    home_dir = Path.home()
    candidates = (
        home_dir / "Downloads" / EXPORT_DIR_NAME,
        home_dir / EXPORT_DIR_NAME,
        Path(tempfile.gettempdir()) / EXPORT_DIR_NAME,
    )
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        return candidate
    raise RuntimeError("Cannot create an export directory in any writable user location.")


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
    export_root = get_export_root()
    export_root.mkdir(parents=True, exist_ok=True)
    output_path = export_root / f"caye_export_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"

    try:
        process_image(input_path, output_path, options, reporter=reporter)
        status = "\n".join(messages)
        return str(output_path), status
    except Exception as exc:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None, f"错误：{exc}"


def run_export_download(*args):
    gr = import_gradio()
    output_path, status = run_export(*args)
    if output_path is None:
        raise gr.Error(status)
    return gr.update(value=output_path), status


def render_section_header(step: str, title: str, copy: str) -> str:
    return (
        "<div class='caye-section-head'>"
        "<div class='caye-section-title'>"
        f"<span class='caye-section-kicker'>{step}</span>"
        f"<h3>{title}</h3>"
        "</div>"
        f"<p>{copy}</p>"
        "</div>"
    )


def create_ui() -> gr.Blocks:
    gr = import_gradio()
    blocks_kwargs = {
        "title": "CAYE 水印工具",
        "fill_width": True,
    }
    if supports_parameter(gr.Blocks, "css"):
        blocks_kwargs["css"] = APP_CSS

    with gr.Blocks(**blocks_kwargs) as app:
        current_input = gr.State(None)
        export_root_text = f"导出结果会保存到 <code>{get_export_root()}</code>"

        with gr.Row(elem_classes=["caye-main-grid"]):
            with gr.Column(scale=6, min_width=320, elem_classes=["caye-stack"]):
                with gr.Group(elem_classes=["caye-panel"]):
                    gr.Markdown(
                        render_section_header(
                            "Step 1",
                            "导入",
                            "上传 DNG，先确认读图正常。",
                        ),
                    )
                    with gr.Row(elem_classes=["caye-upload-shell"]):
                        with gr.Column(elem_classes=["caye-uploader-card", "caye-stack"]):
                            gr.Markdown(
                                "<p class='caye-subtitle'>支持拖拽或点击上传。</p>"
                            )
                            input_file = gr.File(
                                label="拖入或点击 DNG",
                                file_count="single",
                                file_types=[".dng"],
                                type="filepath",
                                height=208,
                                interactive=True,
                                elem_classes=["caye-dropzone"],
                            )
                            gr.Markdown(
                                "<p class='caye-upload-note'>仅支持 <code>.DNG</code>。后续参数会直接作用到当前原片。</p>"
                            )
                        with gr.Column(elem_classes=["caye-side-preview-card"]):
                            input_render = gr.Image(
                                label="原片预览",
                                type="pil",
                                height=360,
                                interactive=False,
                                elem_classes=["caye-dng-preview"],
                            )

                with gr.Group(elem_classes=["caye-panel"]):
                    gr.Markdown(
                        render_section_header(
                            "Step 2",
                            "参数",
                            "设置模板、信息和增强选项。",
                        ),
                    )
                    with gr.Group(elem_classes=["caye-fieldset"]):
                        gr.Markdown("<h4 class='caye-subsection-title'>模板与品牌</h4>")
                        with gr.Row(elem_classes=["caye-form-grid"]):
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
                        no_watermark = gr.Checkbox(label="不添加水印", value=False)
                        gr.Markdown(
                            "<p class='caye-helper'>只看修复效果时，可勾选“不添加水印”。</p>"
                        )
                    with gr.Group(elem_classes=["caye-fieldset"]):
                        gr.Markdown("<h4 class='caye-subsection-title'>EXIF 信息</h4>")
                        with gr.Row(elem_classes=["caye-form-row"]):
                            camera_model = gr.Textbox(
                                label="相机型号",
                                value="沧野C3 Mark I",
                                placeholder="例如：沧野C3 Mark I",
                            )
                            lens_model = gr.Textbox(label="镜头型号", placeholder="例如：RF 50mm f/1.2L")
                        with gr.Row(elem_classes=["caye-form-row"]):
                            focal_length_35mm = gr.Textbox(
                                label="焦距",
                                placeholder="例如：50mm",
                                scale=1,
                                min_width=140,
                            )
                            captured_at = gr.Textbox(
                                label="拍摄日期",
                                placeholder="例如：2024-06-15",
                                scale=2,
                                min_width=240,
                                elem_classes=["caye-date-field"],
                            )
                        with gr.Row(elem_classes=["caye-form-row"]):
                            aperture = gr.Textbox(label="光圈", placeholder="例如：2.8")
                            shutter_speed = gr.Textbox(label="快门速度", placeholder="例如：125、400、8000")
                            iso = gr.Textbox(label="ASA", value="100", placeholder="例如：100")
                        gr.Markdown(
                            "<p class='caye-helper'>这些字段只影响页脚展示，留空会自动折叠。</p>"
                        )
                    with gr.Group(elem_classes=["caye-fieldset"]):
                        gr.Markdown("<h4 class='caye-subsection-title'>增强设置</h4>")
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
                        gr.Markdown(
                            "<p class='caye-helper'><strong>推荐：</strong>4x + balanced + 0.22。更干净可选 clean。</p>"
                        )
                    preview_inputs = [
                        current_input, template, logo_choice, logo_upload, upscale_factor,
                        restoration_profile, watermark_scale, opacity, no_watermark,
                        camera_model, lens_model, focal_length_35mm,
                        aperture, shutter_speed, iso, captured_at,
                    ]
                    with gr.Group(elem_classes=["caye-action-bar"]):
                        with gr.Row(elem_classes=["caye-action-row"]):
                            preview_btn = gr.Button("生成预览", variant="secondary")
                            export_btn = gr.DownloadButton(
                                label="导出 PNG",
                                value=None,
                                variant="primary",
                                elem_classes=["caye-download"],
                            )
                        gr.Markdown(
                            "<p class='caye-helper'>先预览，确认无误后再导出。</p>"
                        )

            with gr.Column(scale=6, min_width=320, elem_classes=["caye-stack", "caye-stage-column"]):
                with gr.Group(elem_classes=["caye-panel"]):
                    gr.Markdown(
                        render_section_header(
                            "Step 3",
                            "预览",
                            "查看当前成片。",
                        ),
                    )
                    preview_image = gr.Image(
                        label="成片预览",
                        type="pil",
                        height=640,
                        elem_classes=["caye-output-preview"],
                    )
                    gr.Markdown(
                        "<p class='caye-preview-note'>修改参数后，重新点击“生成预览”即可刷新结果。</p>"
                    )
                with gr.Group(elem_classes=["caye-panel", "caye-status-panel"]):
                    gr.Markdown(
                        render_section_header(
                            "Step 4",
                            "状态",
                            "查看日志和导出位置。",
                        )
                    )
                    gr.Markdown(
                        f"<p class='caye-helper caye-inline-path'>{export_root_text}</p>"
                    )
                    status_text = gr.Textbox(
                        label="状态",
                        lines=8,
                        value="等待导入 DNG。",
                        interactive=False,
                        elem_classes=["caye-status"],
                    )

        def toggle_custom_logo(choice: str):
            return gr.update(visible=choice == CUSTOM_LOGO_CHOICE)

        logo_choice.change(
            fn=toggle_custom_logo,
            inputs=[logo_choice],
            outputs=[logo_upload],
        )

        input_file.change(
            fn=render_dng_input,
            inputs=[input_file],
            outputs=[current_input, input_render, status_text],
        )

        preview_btn.click(
            fn=run_preview,
            inputs=preview_inputs,
            outputs=[preview_image, status_text],
        )

        export_btn.click(
            fn=run_export_download,
            inputs=preview_inputs,
            outputs=[export_btn, status_text],
        )

    return app


def launch_app() -> None:
    gr = import_gradio()
    app = create_ui()
    server_name = "127.0.0.1"
    server_port = find_available_port(server_name)
    url = f"http://{server_name}:{server_port}"
    print(f"CAYE 水印工具正在启动：{url}", flush=True)
    if os.environ.get("CAYE_WATERMARK_NO_BROWSER") != "1":
        open_browser_later(url)
    launch_kwargs = {
        "server_name": server_name,
        "server_port": server_port,
        "theme": gr.themes.Soft(
            primary_hue=gr.themes.colors.emerald,
            secondary_hue=gr.themes.colors.cyan,
            neutral_hue=gr.themes.colors.slate,
            radius_size=gr.themes.sizes.radius_lg,
            text_size=gr.themes.sizes.text_md,
        ),
        "inbrowser": False,
        "prevent_thread_lock": False,
    }
    if supports_parameter(app.launch, "css"):
        launch_kwargs["css"] = APP_CSS
    app.launch(**launch_kwargs)


if __name__ == "__main__":
    launch_app()
