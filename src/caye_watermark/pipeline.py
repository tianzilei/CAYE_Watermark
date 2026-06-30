from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

if TYPE_CHECKING:
    import rawpy

TEMPLATES = (
    "logo-stamp",
    "logo-chip",
    "logo-outline",
    "standard-footer",
    "standard-footer-2",
    "center-logo",
)

RESTORATION_PROFILES = (
    "detail",
    "balanced",
    "clean",
)

StageReporter = Callable[[str, str], None]
WORKING_WHITE_LEVEL = 255.0
RAW_WHITE_LEVEL = 65535.0

# ITU-R BT.601 luminance coefficients
LUMA_R = 0.299
LUMA_G = 0.587
LUMA_B = 0.114

# Edge detection
EDGE_DETECT_THRESHOLD = 36.0
EDGE_MAX_TRIM_RATIO = 20  # width // 20
EDGE_MAX_TRIM_ABS = 12

# Super-resolution
SR_BACKPROJECT_GAIN = 0.7
SR_FINE_DETAIL_WEIGHT = 0.95
SR_MID_DETAIL_WEIGHT = 0.55
SR_EDGE_MASK_POWER = 0.82
SR_DETAIL_MASK_POWER = 0.9
SR_DETAIL_FLOOR_RATIO = 0.18
SR_DETAIL_PEAK_RATIO = 0.82
SR_STRUCTURE_EDGE_WEIGHT = 0.7
SR_STRUCTURE_DETAIL_WEIGHT = 0.3
SR_BLUR_SMALL_RADIUS = 0.7
SR_BLUR_LARGE_RADIUS = 1.6

# Sharpness
SHARPNESS_BOOST_MULTIPLIER = 1.2
SHARPNESS_BLUR_RADIUS = 0.85

# Local balance
LOCAL_BALANCE_MIN_STRENGTH = 0.12
LOCAL_BALANCE_BRIGHTNESS_MULTIPLIER = 1.9
LOCAL_BALANCE_COLOR_SHIFT_MULTIPLIER = 8.5
LOCAL_BALANCE_INNER_RADIUS = 0.18
LOCAL_BALANCE_GAIN_MIN = 0.82
LOCAL_BALANCE_GAIN_MAX = 1.22

# Color cast
CAST_GAIN_MIN = 0.82
CAST_GAIN_MAX = 1.18
CAST_WARM_THRESHOLD = 0.018
CAST_GREEN_THRESHOLD = 0.015
CAST_MODERATE_THRESHOLD = 0.035
CAST_STRONG_THRESHOLD = 0.07
CAST_MIN_SAMPLES = 250
CAST_SATURATION_THRESHOLD = 0.28

# Font sizing
FONT_HEIGHT_SCALE = 1.35
FONT_SIZE_MIN = 8

FONT_SEARCH_DIRS = (
    Path("/System/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"),
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
)

DEFAULT_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

BOLD_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)

FONT_NAME_ALIASES = {
    "AlibabaPuHuiTi-2-85-Bold.otf": BOLD_FONT_CANDIDATES,
    "AlibabaPuHuiTi-2-55-Regular.otf": DEFAULT_FONT_CANDIDATES,
}


@dataclass(frozen=True)
class ProcessingOptions:
    template: str = "logo-stamp"
    watermark_image: Path | None = None
    enable_watermark: bool = True
    position: str = "bottom-left"
    upscale_factor: int = 4
    restoration_profile: str = "balanced"
    contrast: float = 1.02
    color: float = 1.01
    sharpness: float = 1.08
    watermark_scale: float = 0.22
    opacity: int = 235
    manual_exif: ManualExif = field(default_factory=lambda: ManualExif())


@dataclass(frozen=True)
class ManualExif:
    camera_model: str = ""
    lens_model: str = ""
    focal_length_35mm: str = ""
    aperture: str = ""
    shutter_speed: str = ""
    iso: str = ""
    captured_at: str = ""


@dataclass(frozen=True)
class RestorationSettings:
    fbdd: str
    median_filter_passes: int
    noise_thr: float | None
    post_median_size: int
    sharpness: float
    contrast: float
    color: float
    cast_correction_strength: float
    local_balance_strength: float
    tone_strength: float
    superres_strength: float
    backprojection_passes: int


@dataclass(frozen=True)
class ColorCastAnalysis:
    label: str
    severity: str
    gains: tuple[float, float, float]
    channel_means: tuple[float, float, float]


@dataclass(frozen=True)
class EdgeCropAnalysis:
    left: int
    right: int
    top: int
    bottom: int


@dataclass(frozen=True)
class LocalBalanceAnalysis:
    applied: bool
    strength: float
    brightness_ratio: float
    color_shift: float


@dataclass(frozen=True)
class SuperResolutionAnalysis:
    applied: bool
    factor: int
    strength: float
    passes: int


RESTORATION_SETTINGS = {
    "detail": RestorationSettings(
        fbdd="Light",
        median_filter_passes=0,
        noise_thr=None,
        post_median_size=0,
        sharpness=1.12,
        contrast=1.0,
        color=1.0,
        cast_correction_strength=0.35,
        local_balance_strength=0.38,
        tone_strength=0.08,
        superres_strength=0.62,
        backprojection_passes=1,
    ),
    "balanced": RestorationSettings(
        fbdd="Light",
        median_filter_passes=0,
        noise_thr=2.0,
        post_median_size=0,
        sharpness=1.06,
        contrast=1.0,
        color=1.01,
        cast_correction_strength=0.6,
        local_balance_strength=0.58,
        tone_strength=0.12,
        superres_strength=0.78,
        backprojection_passes=2,
    ),
    "clean": RestorationSettings(
        fbdd="Full",
        median_filter_passes=1,
        noise_thr=4.0,
        post_median_size=3,
        sharpness=1.03,
        contrast=1.01,
        color=1.0,
        cast_correction_strength=0.78,
        local_balance_strength=0.72,
        tone_strength=0.42,
        superres_strength=0.58,
        backprojection_passes=2,
    ),
}


def report_status(reporter: StageReporter | None, stage: str, message: str) -> None:
    if reporter is not None:
        reporter(stage, message)

def stringify_template_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def clean_text(value: str | None) -> str:
    return stringify_template_value(value).strip()


def ensure_prefix(value: str, prefix: str) -> str:
    normalized = clean_text(value)
    if not normalized:
        return ""
    if normalized.lower().startswith(prefix.lower()):
        return normalized
    return f"{prefix}{normalized}"


def ensure_suffix(value: str, suffix: str) -> str:
    normalized = clean_text(value)
    if not normalized:
        return ""
    if normalized.lower().endswith(suffix.lower()):
        return normalized
    return f"{normalized}{suffix}"


def format_capture_details(metadata: ManualExif) -> str:
    parts = []
    focal = clean_text(metadata.focal_length_35mm)
    if focal:
        parts.append(focal)

    aperture = ensure_prefix(metadata.aperture, "f/")
    if aperture:
        parts.append(aperture)

    shutter = ensure_suffix(metadata.shutter_speed, "s")
    if shutter:
        parts.append(shutter)

    iso = ensure_prefix(metadata.iso, "ISO")
    if iso:
        parts.append(iso)
    return "  ".join(parts)


def parse_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def parse_color(value: Any, default: str = "white") -> tuple[int, int, int, int]:
    color_value = stringify_template_value(value) or default
    return ImageColor.getcolor(color_value, "RGBA")


@lru_cache(maxsize=None)
def resolve_font_path(font_name: str | None, is_bold: bool) -> str | None:
    requested = []
    if font_name:
        requested.append(font_name)
        requested.extend(FONT_NAME_ALIASES.get(font_name, ()))
    requested.extend(BOLD_FONT_CANDIDATES if is_bold else DEFAULT_FONT_CANDIDATES)

    for item in requested:
        candidate = Path(item).expanduser()
        if candidate.is_file():
            return str(candidate)
        filename = candidate.name
        for directory in FONT_SEARCH_DIRS:
            if not directory.exists():
                continue
            direct = directory / filename
            if direct.is_file():
                return str(direct)
            for match in directory.rglob(filename):
                if match.is_file():
                    return str(match)
    return None


def load_font(font_name: str | None, font_size: int, is_bold: bool = False) -> ImageFont.ImageFont:
    resolved = resolve_font_path(font_name, is_bold)
    if resolved:
        try:
            return ImageFont.truetype(resolved, max(8, font_size))
        except OSError:
            pass
    return ImageFont.load_default()


def fit_font_to_height(
    text: str,
    target_height: int,
    font_name: str | None,
    is_bold: bool,
) -> tuple[ImageFont.ImageFont, tuple[int, int, int, int]]:
    sample = text if text.strip() else "Ag"
    probe = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)

    font_size = max(FONT_SIZE_MIN, int(target_height * FONT_HEIGHT_SCALE))
    last_font = load_font(font_name, font_size, is_bold)
    last_bbox = draw.textbbox((0, 0), sample, font=last_font)
    while font_size > 8:
        font = load_font(font_name, font_size, is_bold)
        bbox = draw.textbbox((0, 0), sample, font=font)
        text_height = max(1, bbox[3] - bbox[1])
        last_font, last_bbox = font, bbox
        if text_height <= target_height:
            break
        font_size -= max(1, font_size // 10)
    return last_font, last_bbox


def render_text_segment(segment: dict[str, Any], target_height: int) -> Image.Image:
    text = stringify_template_value(segment.get("text"))
    if not text.strip():
        return Image.new("RGBA", (1, max(1, target_height)), (0, 0, 0, 0))

    font_name = stringify_template_value(segment.get("font_path")) or None
    font, bbox = fit_font_to_height(
        text=text,
        target_height=max(8, target_height),
        font_name=font_name,
        is_bold=bool(segment.get("is_bold")),
    )
    width = max(1, bbox[2] - bbox[0])
    height = max(1, bbox[3] - bbox[1])
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text(
        (-bbox[0], -bbox[1]),
        text,
        font=font,
        fill=parse_color(segment.get("color"), "#242424"),
    )
    return image


def render_text_block(block: dict[str, Any] | None, default_height: int) -> Image.Image | None:
    block = block or {}
    target_height = max(8, parse_int(block.get("height"), default_height))
    if "text_segments" in block:
        segments = [
            {
                "text": stringify_template_value(item.get("text")),
                "color": item.get("color", block.get("color", "#242424")),
                "font_path": item.get("font_path", block.get("font_path")),
                "is_bold": item.get("is_bold", block.get("is_bold", False)),
            }
            for item in block.get("text_segments", [])
            if clean_text(item.get("text"))
        ]
    else:
        segments = []
        if clean_text(block.get("text")):
            segments.append(
                {
                    "text": stringify_template_value(block.get("text")),
                    "color": block.get("color", "#242424"),
                    "font_path": block.get("font_path"),
                    "is_bold": block.get("is_bold", False),
                }
            )

    if not segments:
        return None

    rendered = [render_text_segment(segment, target_height) for segment in segments]
    spacing = max(4, target_height // 7)
    width = sum(item.width for item in rendered) + spacing * max(0, len(rendered) - 1)
    height = max([target_height, *(item.height for item in rendered)])
    canvas = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))

    cursor_x = 0
    for item in rendered:
        cursor_y = canvas.height - item.height
        canvas.alpha_composite(item, (cursor_x, cursor_y))
        cursor_x += item.width + spacing
    return canvas


def measure_block_stack(
    blocks: list[Image.Image | None],
    spacing: int,
) -> tuple[list[Image.Image], int, int]:
    visible_blocks = [block for block in blocks if block is not None]
    if not visible_blocks:
        return [], 0, 0
    total_height = sum(block.height for block in visible_blocks)
    total_height += spacing * max(0, len(visible_blocks) - 1)
    max_width = max(block.width for block in visible_blocks)
    return visible_blocks, max_width, total_height


def compute_stack_positions(
    blocks: list[Image.Image],
    width: int,
    footer_start_y: int,
    footer_height: int,
    spacing: int,
    align: str,
    right_limit_x: int,
) -> list[tuple[Image.Image, int, int]]:
    if not blocks:
        return []

    content_height = sum(block.height for block in blocks) + spacing * max(0, len(blocks) - 1)
    cursor_y = footer_start_y + max(0, (footer_height - content_height) // 2)
    positions = []
    for block in blocks:
        if align == "right":
            x = right_limit_x - block.width
        else:
            x = right_limit_x - width
        positions.append((block, x, cursor_y))
        cursor_y += block.height + spacing
    return positions


def resize_to_height(image: Image.Image, height: int) -> Image.Image:
    if height <= 0:
        return image
    scale = height / float(image.height)
    return image.resize(
        (max(1, int(image.width * scale)), max(1, height)),
        Image.Resampling.LANCZOS,
    )


def resolve_template_asset_path(raw_path: Any) -> Path | None:
    path_text = stringify_template_value(raw_path).strip()
    if not path_text:
        return None
    candidate = Path(path_text).expanduser()
    return candidate.resolve()


def load_template_logo(raw_path: Any, opacity: int) -> Image.Image | None:
    path = resolve_template_asset_path(raw_path)
    if path is None:
        return None
    if not path.is_file():
        raise FileNotFoundError(f"Template logo file does not exist: {path}")
    with Image.open(path) as handle:
        logo = handle.convert("RGBA")
    return apply_opacity(logo, opacity)


def normalize_alignment(value: Any) -> str:
    alignment = stringify_template_value(value).strip().lower()
    if alignment in {"left", "right"}:
        return alignment
    return "right"


def render_builtin_footer_template(
    base: Image.Image,
    definition: dict[str, Any],
    options: ProcessingOptions,
) -> Image.Image:
    left_margin = parse_int(definition.get("left_margin"), 0)
    right_margin = parse_int(definition.get("right_margin"), 0)
    top_margin = parse_int(definition.get("top_margin"), 0)
    footer_height = parse_int(definition.get("bottom_margin"), int(base.height * 0.12))
    default_text_height = max(16, int(footer_height * 0.3))
    middle_spacing = parse_int(
        definition.get("middle_spacing"),
        max(4, int(footer_height * 0.05)),
    )

    left_top = render_text_block(definition.get("left_top"), default_text_height)
    left_bottom = render_text_block(definition.get("left_bottom"), default_text_height)
    right_top = render_text_block(definition.get("right_top"), default_text_height)
    right_bottom = render_text_block(definition.get("right_bottom"), default_text_height)

    left_blocks, left_width, left_height = measure_block_stack(
        [left_top, left_bottom],
        middle_spacing,
    )
    right_blocks, right_width, right_height = measure_block_stack(
        [right_top, right_bottom],
        middle_spacing,
    )
    text_column_height = max(left_height, right_height)
    footer_padding = max(14, default_text_height // 2)
    center_logo_height = parse_int(
        definition.get("center_logo_height", definition.get("center_height")),
        0,
    )
    if center_logo_height > 0:
        footer_height = max(footer_height, center_logo_height + footer_padding * 2)
    footer_height = max(footer_height, text_column_height + footer_padding * 2)

    canvas_width = base.width + left_margin + right_margin
    canvas_height = base.height + top_margin + footer_height
    common_spacing = max(12, int(canvas_width * 0.02))
    footer_start_y = top_margin + base.height

    canvas = Image.new(
        "RGBA",
        (canvas_width, canvas_height),
        parse_color(definition.get("color"), "white"),
    )
    canvas.paste(base, (left_margin, top_margin), mask=base if base.mode == "RGBA" else None)

    left_logo = load_template_logo(definition.get("left_logo"), options.opacity)
    right_logo = load_template_logo(definition.get("right_logo"), options.opacity)
    center_logo = load_template_logo(definition.get("center_logo"), options.opacity)

    left_logo_width = 0
    if left_logo:
        left_logo = resize_to_height(left_logo, footer_height)
        left_logo_y = footer_start_y + max(0, (footer_height - left_logo.height) // 2)
        canvas.alpha_composite(left_logo, (left_margin, left_logo_y))
        left_logo_width = left_logo.width

    if center_logo:
        target_height = center_logo_height if center_logo_height > 0 else footer_height
        center_logo = resize_to_height(center_logo, target_height)
        center_x = (canvas.width - center_logo.width) // 2
        center_y = footer_start_y + ((footer_height - center_logo.height) // 2)
        canvas.alpha_composite(center_logo, (center_x, center_y))

    left_x = left_margin + left_logo_width + common_spacing
    for block, _, y in compute_stack_positions(
        left_blocks,
        left_width,
        footer_start_y,
        footer_height,
        middle_spacing,
        "left",
        left_x + left_width,
    ):
        canvas.alpha_composite(block, (left_x, y))

    if right_logo:
        logo_size = max(default_text_height * 2, text_column_height)
        right_logo = resize_to_height(right_logo, logo_size)
        right_logo_x = canvas_width - right_margin - right_logo.width
        right_logo_y = footer_start_y + max(0, (footer_height - right_logo.height) // 2)
        canvas.alpha_composite(right_logo, (right_logo_x, right_logo_y))

        if right_blocks:
            delimiter_width = parse_int(
                definition.get("delimiter_width"),
                max(2, int(base.width * 0.003)),
            )
            delimiter = Image.new(
                "RGBA",
                (delimiter_width, max(1, int(logo_size * 1.1))),
                parse_color(definition.get("delimiter_color"), "#D8D8D6"),
            )
            delimiter_x = right_logo_x - common_spacing - delimiter.width
            delimiter_y = footer_start_y + max(0, (footer_height - delimiter.height) // 2)
            canvas.alpha_composite(delimiter, (delimiter_x, delimiter_y))
            right_text_limit_x = delimiter_x - common_spacing
        else:
            right_text_limit_x = canvas_width - right_margin
    else:
        right_text_limit_x = canvas_width - right_margin

    for block, x, y in compute_stack_positions(
        right_blocks,
        right_width,
        footer_start_y,
        footer_height,
        middle_spacing,
        normalize_alignment(definition.get("right_alignment")),
        right_text_limit_x,
    ):
        canvas.alpha_composite(block, (x, y))

    return canvas


def _build_footer_definition(
    base: Image.Image,
    input_path: Path,
    options: ProcessingOptions,
    *,
    camera_color: str = "black",
    lens_color: str = "#242424",
    details_color: str = "#242424",
    time_color: str = "#242424",
    delimiter_color: str = "#D8D8D6",
    right_alignment: str = "left",
    left_margin: int | None = None,
    right_margin: int | None = None,
    top_margin: int | None = None,
    bottom_margin: int | None = None,
    details_fallback_suffix: str = "PNG",
    time_fallback_template: str | None = None,
) -> dict[str, Any]:
    camera_label = clean_text(options.manual_exif.camera_model)
    lens_label = clean_text(options.manual_exif.lens_model)
    capture_details = format_capture_details(options.manual_exif)
    capture_time = clean_text(options.manual_exif.captured_at)

    definition: dict[str, Any] = {
        "left_top": {
            "text_segments": [
                {
                    "text": camera_label,
                    "color": camera_color,
                    "font_path": "AlibabaPuHuiTi-2-85-Bold.otf",
                    "is_bold": True,
                }
            ]
        },
        "left_bottom": {
            "text": lens_label,
            "color": lens_color,
        },
        "right_top": {
            "text": capture_details or f"{base.width}x{base.height} {details_fallback_suffix}",
            "font_path": "AlibabaPuHuiTi-2-85-Bold.otf",
            "color": details_color,
        },
        "right_bottom": {
            "text": capture_time
            or (time_fallback_template or f"{options.restoration_profile.upper()} · {options.upscale_factor}X"),
            "color": time_color,
        },
        "right_logo": str(options.watermark_image) if options.watermark_image else "",
        "delimiter_color": delimiter_color,
        "right_alignment": right_alignment,
        "color": "white",
    }

    if left_margin is not None:
        definition["left_margin"] = left_margin
    if right_margin is not None:
        definition["right_margin"] = right_margin
    if top_margin is not None:
        definition["top_margin"] = top_margin
    if bottom_margin is not None:
        definition["bottom_margin"] = bottom_margin

    return definition


def build_standard_footer_definition(
    base: Image.Image,
    input_path: Path,
    options: ProcessingOptions,
) -> dict[str, Any]:
    return _build_footer_definition(base, input_path, options)


def build_standard_footer_2_definition(
    base: Image.Image,
    input_path: Path,
    options: ProcessingOptions,
) -> dict[str, Any]:
    margin_x = max(20, int(base.width * 0.03))
    margin_y = max(20, int(base.height * 0.03))
    return _build_footer_definition(
        base,
        input_path,
        options,
        camera_color="#111111",
        lens_color="#4B4B4B",
        details_color="#111111",
        time_color="#4B4B4B",
        delimiter_color="#FFFFFF00",
        left_margin=margin_x,
        right_margin=margin_x,
        top_margin=margin_y,
        bottom_margin=max(44, int(base.height * 0.11)),
        details_fallback_suffix="",
        time_fallback_template=f"{base.width}x{base.height} · {options.restoration_profile.upper()}",
    )


def build_center_logo_definition(
    base: Image.Image,
    options: ProcessingOptions,
) -> dict[str, Any]:
    return {
        "left_top": {"text": ""},
        "left_bottom": {"text": ""},
        "right_top": {"text": ""},
        "right_bottom": {"text": ""},
        "center_logo": str(options.watermark_image) if options.watermark_image else "",
        "center_height": max(18, int(base.height * 0.02)),
        "left_margin": max(18, int(base.height * 0.02)),
        "right_margin": max(18, int(base.height * 0.02)),
    }


def render_styled_template(
    base: Image.Image,
    input_path: Path,
    options: ProcessingOptions,
) -> Image.Image:
    if options.template == "standard-footer":
        definition = build_standard_footer_definition(base, input_path, options)
    elif options.template == "standard-footer-2":
        definition = build_standard_footer_2_definition(base, input_path, options)
    elif options.template == "center-logo":
        definition = build_center_logo_definition(base, options)
    else:
        raise ValueError(f"Unsupported template: {options.template}")
    return render_builtin_footer_template(base, definition, options)


def get_restoration_settings(profile: str) -> RestorationSettings:
    try:
        return RESTORATION_SETTINGS[profile]
    except KeyError as exc:
        raise ValueError(f"Unsupported restoration profile: {profile}") from exc


def import_rawpy():
    try:
        import rawpy
    except ImportError as exc:
        raise RuntimeError(
            "rawpy is required to decode DNG files. Install project dependencies "
            "with `pip install -e .` before processing photos."
        ) from exc
    return rawpy


def load_image(path: Path, settings: RestorationSettings) -> np.ndarray:
    if path.suffix.lower() != ".dng":
        raise ValueError("Only .DNG input files are supported.")

    rawpy = import_rawpy()
    fbdd_noise_reduction = getattr(rawpy.FBDDNoiseReductionMode, settings.fbdd)
    with rawpy.imread(str(path)) as raw:
        rgb = raw.postprocess(
            use_camera_wb=True,
            no_auto_bright=True,
            demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
            highlight_mode=rawpy.HighlightMode.Blend,
            fbdd_noise_reduction=fbdd_noise_reduction,
            median_filter_passes=settings.median_filter_passes,
            noise_thr=settings.noise_thr,
            output_bps=16,
        )
    mirrored = np.flip(rgb, axis=1).astype(np.float32)
    return mirrored * (WORKING_WHITE_LEVEL / RAW_WHITE_LEVEL)


def channel_distance(
    sample_a: tuple[float, float, float],
    sample_b: tuple[float, float, float],
) -> float:
    return max(abs(sample_a[i] - sample_b[i]) for i in range(3))


def detect_edge_crop(image: np.ndarray) -> EdgeCropAnalysis:
    height, width = image.shape[:2]
    if width < 32 or height < 32:
        return EdgeCropAnalysis(0, 0, 0, 0)

    arr = image.astype(np.float32, copy=False)
    probe = min(16, max(4, width // 24))
    ref_band = min(8, max(3, width // 80))
    inner_left_x = min(width - ref_band, probe + 6)
    inner_right_x = max(0, width - probe - 6 - ref_band)
    segment_edges = (0, height // 3, (height * 2) // 3, height)

    def strip_mean(x0: int, x1: int, y0: int, y1: int) -> tuple[float, float, float]:
        region = arr[y0:y1, x0:x1]
        return tuple(region.mean(axis=(0, 1)))

    def column_distance(x0: int, x1: int, ref_x0: int, ref_x1: int) -> float:
        distances = []
        for y0, y1 in zip(segment_edges[:-1], segment_edges[1:]):
            current = strip_mean(x0, x1, y0, y1)
            reference = strip_mean(ref_x0, ref_x1, y0, y1)
            distances.append(channel_distance(current, reference))
        return max(distances)

    threshold = EDGE_DETECT_THRESHOLD
    max_trim = min(EDGE_MAX_TRIM_ABS, width // EDGE_MAX_TRIM_RATIO)
    left_trim = 0
    for x in range(max_trim):
        if column_distance(x, x + 1, inner_left_x, inner_left_x + ref_band) > threshold:
            left_trim = x + 1
        else:
            break

    right_trim = 0
    for offset in range(max_trim):
        x = width - 1 - offset
        if column_distance(x, x + 1, inner_right_x, inner_right_x + ref_band) > threshold:
            right_trim = offset + 1
        else:
            break

    return EdgeCropAnalysis(left=left_trim, right=right_trim, top=0, bottom=0)


def mirrored_edge_block(source: np.ndarray, count: int) -> np.ndarray:
    if count <= 0:
        return source[:, :0, :]
    if source.shape[1] == 0:
        raise ValueError("Source block for edge repair cannot be empty.")
    flipped = np.flip(source, axis=1)
    repeats = (count + flipped.shape[1] - 1) // flipped.shape[1]
    return np.concatenate([flipped] * repeats, axis=1)[:, :count, :]


def repair_abnormal_edges(image: np.ndarray, analysis: EdgeCropAnalysis) -> np.ndarray:
    if not any((analysis.left, analysis.right, analysis.top, analysis.bottom)):
        return image

    repaired = image.copy()
    _, width = repaired.shape[:2]
    if analysis.left > 0 and analysis.left < width:
        left_source = repaired[:, analysis.left : min(width, analysis.left * 2), :]
        repaired[:, : analysis.left, :] = mirrored_edge_block(left_source, analysis.left)
    if analysis.right > 0 and analysis.right < width:
        right_start = max(0, width - (analysis.right * 2))
        right_end = max(0, width - analysis.right)
        right_source = repaired[:, right_start:right_end, :]
        repaired[:, width - analysis.right :, :] = mirrored_edge_block(
            right_source,
            analysis.right,
        )
    return repaired


def array_to_image(array: np.ndarray) -> Image.Image:
    clipped = np.clip(array, 0, 255).astype(np.uint8)
    return Image.fromarray(clipped)


def resize_float_map(channel: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    return np.asarray(
        Image.fromarray(channel.astype(np.float32)).resize(
            size,
            Image.Resampling.BILINEAR,
        ),
        dtype=np.float32,
    )


def luminance_from_array(array: np.ndarray) -> np.ndarray:
    return (array[..., 0] * LUMA_R) + (array[..., 1] * LUMA_G) + (array[..., 2] * LUMA_B)


def resize_rgb_array(array: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    channels = [
        np.asarray(
            Image.fromarray(array[..., index].astype(np.float32)).resize(
                size,
                Image.Resampling.LANCZOS,
            ),
            dtype=np.float32,
        )
        for index in range(3)
    ]
    return np.stack(channels, axis=-1)


def fit_array_within(array: np.ndarray, max_size: int) -> np.ndarray:
    height, width = array.shape[:2]
    if max(height, width) <= max_size:
        return array
    if width >= height:
        target = (max_size, max(1, int(round(height * (max_size / float(width))))))
    else:
        target = (max(1, int(round(width * (max_size / float(height))))), max_size)
    return resize_rgb_array(array, target)


def median_filter_rgb(array: np.ndarray, size: int) -> np.ndarray:
    if size < 3 or size % 2 == 0:
        return array
    pad = size // 2
    padded = np.pad(array, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, (size, size), axis=(0, 1))
    return np.median(windows, axis=(2, 3)).astype(np.float32)


def gaussian_kernel1d(radius: float) -> np.ndarray:
    kernel_radius = max(1, int(np.ceil(radius * 2.0)))
    sigma = max(0.55, radius)
    axis = np.arange(-kernel_radius, kernel_radius + 1, dtype=np.float32)
    kernel = np.exp(-(axis * axis) / (2.0 * sigma * sigma))
    kernel /= kernel.sum()
    return kernel.astype(np.float32)


def convolve_axis(array: np.ndarray, kernel: np.ndarray, axis: int) -> np.ndarray:
    pad = len(kernel) // 2
    pad_width = [(0, 0)] * array.ndim
    pad_width[axis] = (pad, pad)
    padded = np.pad(array, pad_width, mode="reflect")
    result = np.zeros_like(array, dtype=np.float32)
    for offset, weight in enumerate(kernel):
        slices = [slice(None)] * array.ndim
        slices[axis] = slice(offset, offset + array.shape[axis])
        result += padded[tuple(slices)] * float(weight)
    return result


def gaussian_blur_rgb(array: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0:
        return array
    kernel = gaussian_kernel1d(radius)
    blurred = convolve_axis(array, kernel, axis=1)
    return convolve_axis(blurred, kernel, axis=0)


def detect_color_cast(image: np.ndarray) -> ColorCastAnalysis:
    arr = fit_array_within(image.astype(np.float32, copy=False), 160)
    flat = arr.reshape(-1, 3)
    luminance = (flat[:, 0] * LUMA_R) + (flat[:, 1] * LUMA_G) + (flat[:, 2] * LUMA_B)
    low = np.percentile(luminance, 12.0)
    high = np.percentile(luminance, 97.5)
    channel_max = flat.max(axis=1)
    channel_min = flat.min(axis=1)
    saturation = (channel_max - channel_min) / np.maximum(channel_max, 1.0)
    neutral_mask = (luminance >= low) & (luminance <= high) & (saturation <= CAST_SATURATION_THRESHOLD)
    if neutral_mask.sum() < CAST_MIN_SAMPLES:
        neutral_mask = (luminance >= low) & (luminance <= high)
    if neutral_mask.sum() < CAST_MIN_SAMPLES:
        neutral_mask = np.ones(len(flat), dtype=bool)

    red_mean, green_mean, blue_mean = flat[neutral_mask].mean(axis=0)
    average = max(1.0, (red_mean + green_mean + blue_mean) / 3.0)

    warm_score = (red_mean - blue_mean) / average
    green_score = (green_mean - ((red_mean + blue_mean) / 2.0)) / average

    cast_parts = []
    if abs(warm_score) >= CAST_WARM_THRESHOLD:
        cast_parts.append("warm" if warm_score > 0 else "cool")
    if abs(green_score) >= CAST_GREEN_THRESHOLD:
        cast_parts.append("green" if green_score > 0 else "magenta")

    magnitude = max(abs(warm_score), abs(green_score))
    if magnitude < CAST_GREEN_THRESHOLD:
        severity = "neutral"
    elif magnitude < CAST_MODERATE_THRESHOLD:
        severity = "slight"
    elif magnitude < CAST_STRONG_THRESHOLD:
        severity = "moderate"
    else:
        severity = "strong"

    label = "neutral" if not cast_parts else "-".join(cast_parts)
    target = average
    gains = (
        max(CAST_GAIN_MIN, min(CAST_GAIN_MAX, target / max(1.0, red_mean))),
        max(CAST_GAIN_MIN, min(CAST_GAIN_MAX, target / max(1.0, green_mean))),
        max(CAST_GAIN_MIN, min(CAST_GAIN_MAX, target / max(1.0, blue_mean))),
    )
    return ColorCastAnalysis(
        label=label,
        severity=severity,
        gains=gains,
        channel_means=(red_mean, green_mean, blue_mean),
    )


def analyze_local_balance(image: np.ndarray) -> LocalBalanceAnalysis:
    arr = image.astype(np.float32, copy=False)
    height, width, _ = arr.shape
    x0 = width // 4
    x1 = width - x0
    y0 = height // 4
    y1 = height - y0

    center = arr[y0:y1, x0:x1]
    border_x = max(4, width // 7)
    border_y = max(4, height // 7)
    edge_mask = np.zeros((height, width), dtype=bool)
    edge_mask[:, :border_x] = True
    edge_mask[:, width - border_x :] = True
    edge_mask[:border_y, :] = True
    edge_mask[height - border_y :, :] = True
    edges = arr[edge_mask]

    center_mean = center.reshape(-1, 3).mean(axis=0)
    edge_mean = edges.reshape(-1, 3).mean(axis=0)
    center_luma = float(center_mean[0] * LUMA_R + center_mean[1] * LUMA_G + center_mean[2] * LUMA_B)
    edge_luma = float(edge_mean[0] * LUMA_R + edge_mean[1] * LUMA_G + edge_mean[2] * LUMA_B)
    brightness_ratio = edge_luma / max(center_luma, 1.0)

    center_norm = center_mean / max(center_mean.mean(), 1.0)
    edge_norm = edge_mean / max(edge_mean.mean(), 1.0)
    color_shift = float(np.max(np.abs(edge_norm - center_norm)))

    strength = min(1.0, max(abs(1.0 - brightness_ratio) * LOCAL_BALANCE_BRIGHTNESS_MULTIPLIER, color_shift * LOCAL_BALANCE_COLOR_SHIFT_MULTIPLIER))
    return LocalBalanceAnalysis(
        applied=strength >= LOCAL_BALANCE_MIN_STRENGTH,
        strength=strength,
        brightness_ratio=brightness_ratio,
        color_shift=color_shift,
    )


def apply_local_balance_correction(
    image: np.ndarray,
    settings: RestorationSettings,
) -> tuple[np.ndarray, LocalBalanceAnalysis]:
    analysis = analyze_local_balance(image)
    if not analysis.applied or settings.local_balance_strength <= 0:
        return image, analysis

    arr = image.astype(np.float32, copy=False)
    height, width, _ = arr.shape
    small_width = max(24, width // 18)
    small_height = max(18, height // 18)
    small_arr = resize_rgb_array(arr, (small_width, small_height))

    center = small_arr[
        small_height // 4 : small_height - (small_height // 4),
        small_width // 4 : small_width - (small_width // 4),
    ]
    center_reference = center.reshape(-1, 3).mean(axis=0)

    gain_channels = []
    for index in range(3):
        gain_small = center_reference[index] / np.clip(small_arr[..., index], 1.0, None)
        gain_small = np.clip(gain_small, LOCAL_BALANCE_GAIN_MIN, LOCAL_BALANCE_GAIN_MAX)
        gain_channels.append(resize_float_map(gain_small, (width, height)))
    gain_map = np.stack(gain_channels, axis=-1)

    yy, xx = np.ogrid[:height, :width]
    normalized_x = (xx - ((width - 1) / 2.0)) / max(width / 2.0, 1.0)
    normalized_y = (yy - ((height - 1) / 2.0)) / max(height / 2.0, 1.0)
    radius = np.sqrt((normalized_x * normalized_x) + (normalized_y * normalized_y))
    mask = np.clip((radius - LOCAL_BALANCE_INNER_RADIUS) / (1.0 - LOCAL_BALANCE_INNER_RADIUS), 0.0, 1.0)
    mask = mask * mask * (3.0 - (2.0 * mask))

    strength = min(1.0, analysis.strength * settings.local_balance_strength)
    corrected = arr * (1.0 + ((gain_map - 1.0) * mask[..., None] * strength))
    return np.clip(corrected, 0.0, WORKING_WHITE_LEVEL), LocalBalanceAnalysis(
        applied=True,
        strength=strength,
        brightness_ratio=analysis.brightness_ratio,
        color_shift=analysis.color_shift,
    )


def apply_auto_tone_curve(image: np.ndarray, strength: float) -> np.ndarray:
    if strength <= 0:
        return image

    arr = image.astype(np.float32, copy=False)
    flat = arr.reshape(-1, 3)
    luminance = (flat[:, 0] * LUMA_R) + (flat[:, 1] * LUMA_G) + (flat[:, 2] * LUMA_B)
    low = float(np.percentile(luminance, 0.6))
    high = float(np.percentile(luminance, 99.4))
    if high - low < 18.0:
        low = float(np.percentile(luminance, 0.2))
        high = float(np.percentile(luminance, 99.8))

    scale = 255.0 / max(12.0, high - low)
    stretched = np.clip((arr - low) * scale, 0.0, 255.0)

    median_luma = float(np.percentile(luminance, 52.0))
    gamma = 1.0
    if median_luma < 94.0:
        gamma = 0.93
    elif median_luma < 120.0:
        gamma = 0.97
    elif median_luma > 178.0:
        gamma = 1.07
    elif median_luma > 156.0:
        gamma = 1.03

    curved = stretched
    if gamma != 1.0:
        curved = np.power(stretched / 255.0, gamma) * 255.0

    blend = max(0.0, min(1.0, strength))
    corrected = arr + ((curved - arr) * blend)
    return np.clip(corrected, 0.0, WORKING_WHITE_LEVEL)


def reconstruct_super_resolution(
    image: np.ndarray,
    factor: int,
    settings: RestorationSettings,
) -> tuple[np.ndarray, SuperResolutionAnalysis]:
    if factor <= 1:
        return image, SuperResolutionAnalysis(
            applied=False,
            factor=factor,
            strength=0.0,
            passes=0,
        )

    source_arr = image.astype(np.float32, copy=False)
    original_size = (source_arr.shape[1], source_arr.shape[0])
    target_size = (original_size[0] * factor, original_size[1] * factor)

    base_arr = resize_rgb_array(source_arr, target_size)
    refined = base_arr.copy()

    for _ in range(settings.backprojection_passes):
        projected = resize_rgb_array(refined, original_size)
        reconstruction_error = source_arr - projected
        refined += resize_rgb_array(reconstruction_error, target_size) * SR_BACKPROJECT_GAIN

    blur_small = gaussian_blur_rgb(source_arr, radius=SR_BLUR_SMALL_RADIUS)
    blur_large = gaussian_blur_rgb(source_arr, radius=SR_BLUR_LARGE_RADIUS)
    fine_detail = source_arr - blur_small
    mid_detail = blur_small - blur_large
    detail_signal = (fine_detail * SR_FINE_DETAIL_WEIGHT) + (mid_detail * SR_MID_DETAIL_WEIGHT)

    source_luma = luminance_from_array(source_arr)
    detail_luma = luminance_from_array(detail_signal)
    grad_x = np.abs(np.diff(source_luma, axis=1, append=source_luma[:, -1:]))
    grad_y = np.abs(np.diff(source_luma, axis=0, append=source_luma[-1:, :]))
    gradient = np.sqrt((grad_x * grad_x) + (grad_y * grad_y))

    edge_floor = float(np.percentile(gradient, 45.0))
    edge_peak = float(np.percentile(gradient, 97.0))
    edge_mask = np.clip(
        (gradient - edge_floor) / max(1.0, edge_peak - edge_floor),
        0.0,
        1.0,
    )
    edge_mask = np.power(edge_mask, SR_EDGE_MASK_POWER)

    detail_magnitude = np.abs(detail_luma)
    detail_floor = float(np.percentile(detail_magnitude, 55.0))
    detail_peak = float(np.percentile(detail_magnitude, 96.0))
    detail_mask = np.clip(
        (detail_magnitude - detail_floor) / max(1.0, detail_peak - detail_floor),
        0.0,
        1.0,
    )
    detail_mask = np.power(detail_mask, SR_DETAIL_MASK_POWER)

    structure_mask = np.clip((edge_mask * SR_STRUCTURE_EDGE_WEIGHT) + (detail_mask * SR_STRUCTURE_DETAIL_WEIGHT), 0.0, 1.0)
    upscaled_detail = resize_float_map(detail_luma, target_size)
    upscaled_mask = resize_float_map(structure_mask, target_size)
    upscaled_mask = np.clip(upscaled_mask, 0.0, 1.0)

    refined_luma = luminance_from_array(refined)
    detail_gain = settings.superres_strength * (SR_DETAIL_FLOOR_RATIO + (upscaled_mask * SR_DETAIL_PEAK_RATIO))
    reconstructed_luma = refined_luma + (upscaled_detail * detail_gain)

    luma_ratio = (reconstructed_luma + 1e-3) / (refined_luma + 1e-3)
    rebuilt = refined * luma_ratio[..., None]
    return np.clip(rebuilt, 0.0, WORKING_WHITE_LEVEL), SuperResolutionAnalysis(
        applied=True,
        factor=factor,
        strength=settings.superres_strength,
        passes=settings.backprojection_passes,
    )


def apply_color_cast_correction(
    image: np.ndarray,
    analysis: ColorCastAnalysis,
    correction_strength: float,
) -> np.ndarray:
    if analysis.label == "neutral" or correction_strength <= 0:
        return image

    blend_gains = np.array(
        [1.0 + ((gain - 1.0) * correction_strength) for gain in analysis.gains],
        dtype=np.float32,
    )
    corrected = image.astype(np.float32, copy=False) * blend_gains[None, None, :]
    return np.clip(corrected, 0.0, WORKING_WHITE_LEVEL)


def apply_contrast_adjustment(image: np.ndarray, factor: float) -> np.ndarray:
    if abs(factor - 1.0) < 1e-6:
        return image
    midpoint = float(np.percentile(luminance_from_array(image), 50.0))
    adjusted = (image - midpoint) * factor + midpoint
    return np.clip(adjusted, 0.0, WORKING_WHITE_LEVEL)


def apply_color_saturation(image: np.ndarray, factor: float) -> np.ndarray:
    if abs(factor - 1.0) < 1e-6:
        return image
    luma = luminance_from_array(image)[..., None]
    adjusted = luma + ((image - luma) * factor)
    return np.clip(adjusted, 0.0, WORKING_WHITE_LEVEL)


def apply_sharpness_adjustment(image: np.ndarray, factor: float) -> np.ndarray:
    if abs(factor - 1.0) < 1e-6:
        return image
    blurred = gaussian_blur_rgb(image, radius=SHARPNESS_BLUR_RADIUS)
    detail = image - blurred
    if factor > 1.0:
        adjusted = image + (detail * ((factor - 1.0) * SHARPNESS_BOOST_MULTIPLIER))
    else:
        adjusted = image + (detail * (factor - 1.0))
    return np.clip(adjusted, 0.0, WORKING_WHITE_LEVEL)


def optimize_image(
    image: np.ndarray,
    upscale_factor: int,
    settings: RestorationSettings,
    contrast: float,
    color: float,
    sharpness: float,
) -> tuple[
    Image.Image,
    ColorCastAnalysis,
    EdgeCropAnalysis,
    LocalBalanceAnalysis,
    SuperResolutionAnalysis,
]:
    edge_crop = detect_edge_crop(image)
    image = repair_abnormal_edges(image, edge_crop)
    if settings.post_median_size >= 3:
        image = median_filter_rgb(image, settings.post_median_size)
    image, local_balance = apply_local_balance_correction(image, settings)
    analysis = detect_color_cast(image)
    image = apply_color_cast_correction(
        image,
        analysis,
        correction_strength=settings.cast_correction_strength,
    )
    image, superres = reconstruct_super_resolution(image, upscale_factor, settings)
    image = apply_auto_tone_curve(image, settings.tone_strength)
    image = apply_contrast_adjustment(image, settings.contrast * contrast)
    image = apply_color_saturation(image, settings.color * color)
    image = apply_sharpness_adjustment(image, settings.sharpness * sharpness)
    return array_to_image(image).convert("RGBA"), analysis, edge_crop, local_balance, superres


def apply_opacity(image: Image.Image, opacity: int) -> Image.Image:
    layer = image.copy().convert("RGBA")
    alpha = layer.getchannel("A")
    alpha = alpha.point(lambda p: p * max(0, min(255, opacity)) // 255)
    layer.putalpha(alpha)
    return layer


def fit_logo(base_width: int, logo: Image.Image, scale_ratio: float) -> Image.Image:
    target_width = max(1, int(base_width * scale_ratio))
    scale = target_width / float(logo.width)
    size = (target_width, max(1, int(logo.height * scale)))
    return logo.resize(size, Image.Resampling.LANCZOS)


def render_logo(logo_path: Path, base_width: int, scale_ratio: float, opacity: int) -> Image.Image:
    with Image.open(logo_path) as watermark:
        watermark = watermark.convert("RGBA")
    watermark = fit_logo(base_width, watermark, scale_ratio)
    return apply_opacity(watermark, opacity)


def resolve_left_bottom_anchor(
    base_size: tuple[int, int],
    overlay_size: tuple[int, int],
    margin: int,
) -> tuple[int, int]:
    width, height = base_size
    overlay_width, overlay_height = overlay_size
    return margin, max(0, height - overlay_height - margin)


def with_shadow(overlay: Image.Image, blur_radius: int = 12) -> Image.Image:
    shadow = Image.new("RGBA", overlay.size, (255, 255, 255, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (6, 6, overlay.width - 1, overlay.height - 1),
        radius=max(18, overlay.height // 5),
        fill=(0, 0, 0, 78),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur_radius))
    shadow.alpha_composite(overlay)
    return shadow


def add_logo_stamp(base: Image.Image, logo_path: Path, scale_ratio: float, opacity: int) -> Image.Image:
    logo = render_logo(logo_path, base.width, scale_ratio * 0.8, opacity)
    padding = max(24, base.width // 75)
    badge = Image.new(
        "RGBA",
        (logo.width + padding * 2, logo.height + padding * 2),
        (255, 255, 255, 0),
    )
    badge_draw = ImageDraw.Draw(badge)
    badge_draw.rounded_rectangle(
        (0, 0, badge.width, badge.height),
        radius=max(22, badge.height // 4),
        fill=(255, 255, 255, 228),
    )
    badge.alpha_composite(logo, (padding, padding))
    overlay = with_shadow(badge, blur_radius=10)

    margin = max(26, base.width // 42)
    anchor = resolve_left_bottom_anchor(base.size, overlay.size, margin)
    result = base.copy()
    result.alpha_composite(overlay, anchor)
    return result


def add_logo_chip(base: Image.Image, logo_path: Path, scale_ratio: float, opacity: int) -> Image.Image:
    logo = render_logo(logo_path, base.width, scale_ratio, opacity)
    padding_x = max(22, base.width // 70)
    padding_y = max(16, base.width // 90)
    chip = Image.new(
        "RGBA",
        (logo.width + padding_x * 2, logo.height + padding_y * 2),
        (255, 255, 255, 0),
    )
    chip_draw = ImageDraw.Draw(chip)
    chip_draw.rounded_rectangle(
        (0, 0, chip.width, chip.height),
        radius=max(18, chip.height // 3),
        fill=(18, 18, 18, 168),
        outline=(255, 255, 255, 64),
        width=max(2, chip.width // 180),
    )
    chip.alpha_composite(logo, (padding_x, padding_y))

    margin = max(26, base.width // 42)
    anchor = resolve_left_bottom_anchor(base.size, chip.size, margin)
    result = base.copy()
    result.alpha_composite(chip, anchor)
    return result


def add_logo_outline(base: Image.Image, logo_path: Path, scale_ratio: float, opacity: int) -> Image.Image:
    logo = render_logo(logo_path, base.width, scale_ratio * 0.92, opacity)
    padding = max(22, base.width // 75)
    outline = Image.new(
        "RGBA",
        (logo.width + padding * 2, logo.height + padding * 2),
        (255, 255, 255, 0),
    )
    outline_draw = ImageDraw.Draw(outline)
    outline_draw.rounded_rectangle(
        (0, 0, outline.width, outline.height),
        radius=max(20, outline.height // 4),
        fill=(255, 255, 255, 52),
        outline=(255, 255, 255, 210),
        width=max(3, outline.width // 140),
    )
    outline.alpha_composite(logo, (padding, padding))

    margin = max(26, base.width // 42)
    anchor = resolve_left_bottom_anchor(base.size, outline.size, margin)
    result = base.copy()
    result.alpha_composite(outline, anchor)
    return result


_LOGO_TEMPLATE_DISPATCH = {
    "logo-stamp": add_logo_stamp,
    "logo-chip": add_logo_chip,
    "logo-outline": add_logo_outline,
}


def apply_template(
    image: Image.Image,
    options: ProcessingOptions,
    input_path: Path,
) -> Image.Image:
    if not options.enable_watermark:
        return image

    logo_fn = _LOGO_TEMPLATE_DISPATCH.get(options.template)
    if logo_fn is not None:
        if options.watermark_image is None:
            raise ValueError(f"The {options.template} template requires --watermark-image.")
        return logo_fn(
            image,
            options.watermark_image,
            options.watermark_scale,
            options.opacity,
        )

    if options.watermark_image is None:
        raise ValueError(f"The {options.template} template requires --watermark-image.")
    return render_styled_template(image, input_path, options)


def export_image(image: Image.Image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()
    if suffix != ".png":
        raise ValueError("Output file must use the .png extension.")
    image.save(output_path, format="PNG", compress_level=2)


def process_image(
    input_path: Path,
    output_path: Path,
    options: ProcessingOptions,
    reporter: StageReporter | None = None,
) -> Path:
    settings = get_restoration_settings(options.restoration_profile)

    report_status(
        reporter,
        "load",
        f"Loading {input_path.name} with {options.restoration_profile} restoration",
    )
    image = load_image(input_path, settings)

    report_status(
        reporter,
        "restore",
        "Correcting storage artifacts and analyzing color cast",
    )
    image, cast_analysis, edge_crop, local_balance, superres = optimize_image(
        image,
        upscale_factor=options.upscale_factor,
        settings=settings,
        contrast=options.contrast,
        color=options.color,
        sharpness=options.sharpness,
    )
    if any((edge_crop.left, edge_crop.right, edge_crop.top, edge_crop.bottom)):
        report_status(
            reporter,
            "restore",
            f"Repaired abnormal edges: left={edge_crop.left}, right={edge_crop.right}",
        )
    if local_balance.applied:
        report_status(
            reporter,
            "restore",
            (
                "Balanced edge shading and tint: "
                f"brightness={local_balance.brightness_ratio:.2f}, "
                f"shift={local_balance.color_shift:.3f}"
            ),
        )
    if cast_analysis.label == "neutral":
        report_status(reporter, "restore", "Color cast check: neutral")
    else:
        report_status(
            reporter,
            "restore",
            f"Color cast detected: {cast_analysis.severity} {cast_analysis.label}",
        )
    if superres.applied:
        report_status(
            reporter,
            "superres",
            (
                f"Reconstructing {superres.factor}x detail with "
                f"strength={superres.strength:.2f}, passes={superres.passes}"
            ),
        )

    if options.enable_watermark:
        report_status(
            reporter,
            "watermark",
            f"Applying {options.template} watermark template",
        )
        image = apply_template(image, options, input_path)
    else:
        report_status(reporter, "watermark", "Skipping watermark for review export")

    report_status(reporter, "export", f"Exporting {output_path.name}")
    export_image(image, output_path)

    report_status(reporter, "done", f"Saved {output_path}")
    return output_path
