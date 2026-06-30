from __future__ import annotations

import argparse
from pathlib import Path

from caye_watermark.pipeline import (
    ManualExif,
    ProcessingOptions,
    RESTORATION_PROFILES,
    TEMPLATES,
    process_image,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore one DNG photo and export one branded PNG image."
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        required=True,
        help="Path to the input DNG file",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Path to the exported PNG file",
    )
    parser.add_argument(
        "--template",
        choices=TEMPLATES,
        default="logo-stamp",
        help="Brand watermark template",
    )
    parser.add_argument(
        "--watermark-image",
        type=Path,
        default=None,
        help="Path to the logo watermark image",
    )
    parser.add_argument(
        "--no-watermark",
        action="store_true",
        help="Skip watermark rendering and export a clean review PNG",
    )
    parser.add_argument(
        "--upscale-factor",
        type=int,
        choices=(1, 2, 4),
        default=4,
        help="Output upscale factor",
    )
    parser.add_argument(
        "--restoration-profile",
        choices=RESTORATION_PROFILES,
        default="balanced",
        help="Restoration profile for DNG denoise and detail recovery",
    )
    parser.add_argument(
        "--watermark-scale",
        type=float,
        default=0.22,
        help="Logo width relative to the output image width",
    )
    parser.add_argument(
        "--opacity",
        type=int,
        default=235,
        help="Logo opacity between 0 and 255",
    )
    parser.add_argument(
        "--camera-model",
        default="",
        help="Manual EXIF camera model for footer-style templates",
    )
    parser.add_argument(
        "--lens-model",
        default="",
        help="Manual EXIF lens model for footer-style templates",
    )
    parser.add_argument(
        "--focal-length-35mm",
        default="",
        help="Manual EXIF focal length text for footer-style templates",
    )
    parser.add_argument(
        "--aperture",
        default="",
        help="Manual EXIF aperture value, for example 2.8",
    )
    parser.add_argument(
        "--shutter-speed",
        default="",
        help="Manual EXIF shutter speed text, for example 1/125",
    )
    parser.add_argument(
        "--iso",
        default="",
        help="Manual EXIF ISO value, for example 400",
    )
    parser.add_argument(
        "--captured-at",
        default="",
        help="Manual EXIF capture time text for footer-style templates",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable real-time progress messages",
    )
    return parser.parse_args()


def build_output_path(
    input_path: Path,
    output_path: Path | None,
    enable_watermark: bool,
) -> Path:
    if output_path is not None:
        return output_path.expanduser().resolve()

    suffix = "_watermarked.png" if enable_watermark else "_review.png"
    return input_path.with_name(f"{input_path.stem}{suffix}").resolve()


def find_default_logo(input_path: Path) -> Path | None:
    candidates = [
        Path.cwd() / "Example" / "Brands" / "CAYE.png",
        Path.cwd() / "Example" / "Brands" / "CAYE.webp",
        Path.cwd() / "Example" / "Brands" / "Laiye.png",
        input_path.parent / "CAYE.png",
        input_path.parent / "CAYE.webp",
        Path.cwd() / "CAYE.webp",
        input_path.parent / "Laiye.png",
        Path.cwd() / "Laiye.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def validate_args(args: argparse.Namespace) -> argparse.Namespace:
    args.input_file = args.input_file.expanduser().resolve()
    if not args.input_file.exists() or not args.input_file.is_file():
        raise SystemExit(f"Input file does not exist: {args.input_file}")
    if args.input_file.suffix.lower() != ".dng":
        raise SystemExit("Only .DNG input files are supported.")

    args.output_file = build_output_path(
        args.input_file,
        args.output_file,
        enable_watermark=not args.no_watermark,
    )
    if args.output_file.suffix.lower() != ".png":
        raise SystemExit("Output file must use the .png extension.")

    if args.watermark_image is not None:
        args.watermark_image = args.watermark_image.expanduser().resolve()
    elif not args.no_watermark:
        args.watermark_image = find_default_logo(args.input_file)

    if not args.no_watermark and args.watermark_image is None:
        raise SystemExit(
            "A logo file is required. Add CAYE.png to the project or pass --watermark-image."
        )

    if args.watermark_image is not None and not args.watermark_image.exists():
        raise SystemExit(f"Watermark image does not exist: {args.watermark_image}")

    return args


def create_options(args: argparse.Namespace) -> ProcessingOptions:
    return ProcessingOptions(
        template=args.template,
        watermark_image=args.watermark_image,
        enable_watermark=not args.no_watermark,
        upscale_factor=args.upscale_factor,
        restoration_profile=args.restoration_profile,
        watermark_scale=args.watermark_scale,
        opacity=args.opacity,
        manual_exif=ManualExif(
            camera_model=args.camera_model,
            lens_model=args.lens_model,
            focal_length_35mm=args.focal_length_35mm,
            aperture=args.aperture,
            shutter_speed=args.shutter_speed,
            iso=args.iso,
            captured_at=args.captured_at,
        ),
    )


def build_reporter(enabled: bool):
    if not enabled:
        return None

    stage_order = {
        "load": 1,
        "restore": 2,
        "superres": 3,
        "watermark": 4,
        "export": 5,
        "done": 6,
    }

    def reporter(stage: str, message: str) -> None:
        step = stage_order.get(stage, "?")
        print(f"[{step}/6] {message}")

    return reporter


def main() -> None:
    args = validate_args(parse_args())
    options = create_options(args)
    reporter = build_reporter(not args.quiet)
    process_image(args.input_file, args.output_file, options, reporter=reporter)


if __name__ == "__main__":
    main()
