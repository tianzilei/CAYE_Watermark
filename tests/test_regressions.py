from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from caye_watermark._logo import LOGO_CHOICES, find_default_logo, resolve_preset_logo
from caye_watermark.cli import build_output_path, validate_args
from caye_watermark.pipeline import (
    DEFAULT_FONT_CANDIDATES,
    FONT_SEARCH_DIRS,
    EdgeCropAnalysis,
    ManualExif,
    ProcessingOptions,
    apply_opacity,
    detect_edge_crop,
    get_restoration_settings,
    optimize_image,
    parse_color,
    repair_abnormal_edges,
)
from caye_watermark.webui import (
    _validate_dng_file,
    _validate_options,
    build_options,
    cleanup_old_exports,
    render_dng_input,
)


class CliRegressionTests(unittest.TestCase):
    def test_build_output_path_uses_review_suffix_without_watermark(self) -> None:
        path = build_output_path(Path("/tmp/CDI_12.DNG"), None, enable_watermark=False)
        self.assertEqual(path.name, "CDI_12_review.png")

    def test_build_output_path_uses_watermarked_suffix_with_watermark(self) -> None:
        path = build_output_path(Path("/tmp/CDI_12.DNG"), None, enable_watermark=True)
        self.assertEqual(path.name, "CDI_12_watermarked.png")

    def test_build_output_path_uses_explicit_output(self) -> None:
        path = build_output_path(Path("/tmp/CDI_12.DNG"), Path("/out/custom.png"), enable_watermark=True)
        self.assertEqual(path.name, "custom.png")


class CliValidationTests(unittest.TestCase):
    def test_validate_args_rejects_nonexistent_input(self) -> None:
        import argparse
        args = argparse.Namespace(
            input_file=Path("/tmp/nonexistent.DNG"),
            output_file=None,
            no_watermark=True,
            watermark_image=None,
            watermark_scale=0.22,
            opacity=235,
        )
        with self.assertRaises(SystemExit):
            validate_args(args)

    def test_validate_args_rejects_non_dng_extension(self) -> None:
        import argparse
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake")
            tmp = Path(f.name)
        try:
            args = argparse.Namespace(
                input_file=tmp,
                output_file=None,
                no_watermark=True,
                watermark_image=None,
                watermark_scale=0.22,
                opacity=235,
            )
            with self.assertRaises(SystemExit):
                validate_args(args)
        finally:
            tmp.unlink(missing_ok=True)

    def test_validate_args_rejects_invalid_watermark_scale(self) -> None:
        import argparse
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".DNG", delete=False) as f:
            f.write(b"fake")
            tmp = Path(f.name)
        try:
            args = argparse.Namespace(
                input_file=tmp,
                output_file=None,
                no_watermark=True,
                watermark_image=None,
                watermark_scale=1.5,
                opacity=235,
            )
            with self.assertRaises(SystemExit):
                validate_args(args)
        finally:
            tmp.unlink(missing_ok=True)

    def test_validate_args_rejects_invalid_opacity(self) -> None:
        import argparse
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".DNG", delete=False) as f:
            f.write(b"fake")
            tmp = Path(f.name)
        try:
            args = argparse.Namespace(
                input_file=tmp,
                output_file=None,
                no_watermark=True,
                watermark_image=None,
                watermark_scale=0.22,
                opacity=300,
            )
            with self.assertRaises(SystemExit):
                validate_args(args)
        finally:
            tmp.unlink(missing_ok=True)


class LogoTests(unittest.TestCase):
    def test_logo_choices_include_presets_then_custom(self) -> None:
        self.assertEqual(
            LOGO_CHOICES,
            ("CAYE.webp", "HACHIMITSU.png", "LaiyeRed.png", "LaiyeWhite.png", "自选"),
        )

    def test_resolve_preset_logo_finds_brand_file(self) -> None:
        with patch("caye_watermark._logo.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path(__file__).resolve().parents[1]
            result = resolve_preset_logo("HACHIMITSU.png")
            self.assertIsNotNone(result)
            self.assertEqual(result.name, "HACHIMITSU.png")

    def test_find_default_logo_returns_none_when_no_files_exist(self) -> None:
        with patch("caye_watermark._logo.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/nonexistent_dir")
            result = find_default_logo()
            self.assertIsNone(result)


class PipelineRegressionTests(unittest.TestCase):
    def test_importing_pipeline_does_not_require_rawpy(self) -> None:
        settings = get_restoration_settings("balanced")
        self.assertEqual(settings.fbdd, "Light")

    def test_repair_abnormal_edges_preserves_dimensions(self) -> None:
        image = np.zeros((6, 8, 3), dtype=np.float32)
        image[:, 2:, :] = 120.0
        repaired = repair_abnormal_edges(image, EdgeCropAnalysis(left=2, right=0, top=0, bottom=0))
        self.assertEqual(repaired.shape, image.shape)
        self.assertTrue(np.all(repaired[:, :2, :] > 0.0))

    def test_optimize_image_returns_expected_tuple_and_size(self) -> None:
        image = np.linspace(0.0, 255.0, 64 * 48 * 3, dtype=np.float32).reshape(48, 64, 3)
        result, cast, edge, balance, superres = optimize_image(
            image=image,
            upscale_factor=2,
            settings=get_restoration_settings("detail"),
            contrast=1.0,
            color=1.0,
            sharpness=1.0,
        )
        self.assertEqual(result.size, (128, 96))
        self.assertIsInstance(cast.label, str)
        self.assertEqual(edge.left, 0)
        self.assertIsInstance(balance.applied, bool)
        self.assertTrue(superres.applied)

    def test_detect_edge_crop_returns_zero_for_small_images(self) -> None:
        image = np.zeros((16, 16, 3), dtype=np.float32)
        result = detect_edge_crop(image)
        self.assertEqual(result.left, 0)
        self.assertEqual(result.right, 0)

    def test_detect_edge_crop_detects_abnormal_edge(self) -> None:
        image = np.ones((32, 64, 3), dtype=np.float32) * 128.0
        image[:, :3, :] = 0.0
        result = detect_edge_crop(image)
        self.assertGreater(result.left, 0)

    def test_repair_abnormal_edges_noop_when_no_edges(self) -> None:
        image = np.ones((6, 8, 3), dtype=np.float32) * 128.0
        repaired = repair_abnormal_edges(image, EdgeCropAnalysis(0, 0, 0, 0))
        np.testing.assert_array_equal(repaired, image)

    def test_apply_opacity_full_opaque(self) -> None:
        from PIL import Image
        img = Image.new("RGBA", (4, 4), (255, 0, 0, 128))
        result = apply_opacity(img, 255)
        alpha = result.getchannel("A")
        self.assertEqual(alpha.getpixel((0, 0)), 128)

    def test_apply_opacity_zero_transparent(self) -> None:
        from PIL import Image
        img = Image.new("RGBA", (4, 4), (255, 0, 0, 128))
        result = apply_opacity(img, 0)
        alpha = result.getchannel("A")
        self.assertEqual(alpha.getpixel((0, 0)), 0)


class RestorationSettingsTests(unittest.TestCase):
    def test_get_restoration_settings_valid_profile(self) -> None:
        for profile in ("detail", "balanced", "clean"):
            settings = get_restoration_settings(profile)
            self.assertIsNotNone(settings)

    def test_get_restoration_settings_invalid_profile(self) -> None:
        with self.assertRaises(ValueError):
            get_restoration_settings("nonexistent")


class ParseColorTests(unittest.TestCase):
    def test_parse_color_named(self) -> None:
        r, g, b, a = parse_color("red")
        self.assertEqual((r, g, b), (255, 0, 0))
        self.assertEqual(a, 255)

    def test_parse_color_hex(self) -> None:
        r, g, b, a = parse_color("#FF0000")
        self.assertEqual((r, g, b), (255, 0, 0))

    def test_parse_color_none_uses_default(self) -> None:
        r, g, b, a = parse_color(None, "blue")
        self.assertEqual((r, g, b), (0, 0, 255))


class WebUiValidationTests(unittest.TestCase):
    def test_windows_font_candidates_are_configured(self) -> None:
        font_paths = {str(path) for path in FONT_SEARCH_DIRS}
        self.assertIn("C:\\Windows\\Fonts", {path.replace("/", "\\") for path in font_paths})
        candidates = {path.replace("/", "\\").lower() for path in DEFAULT_FONT_CANDIDATES}
        self.assertIn("c:\\windows\\fonts\\msyh.ttc", candidates)

    def test_build_options_uses_selected_preset_logo(self) -> None:
        options = build_options(
            "standard-footer",
            "LaiyeRed.png",
            None,
            4,
            "balanced",
            0.22,
            235,
            False,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )
        self.assertIsNotNone(options.watermark_image)
        self.assertEqual(options.watermark_image.name, "LaiyeRed.png")

    def test_build_options_uses_custom_logo_when_selected(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = Path(f.name)
        try:
            options = build_options(
                "standard-footer",
                "自选",
                str(tmp),
                4,
                "balanced",
                0.22,
                235,
                False,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            )
            self.assertEqual(options.watermark_image, tmp)
        finally:
            tmp.unlink(missing_ok=True)

    def test_validate_dng_file_accepts_existing_dng(self) -> None:
        input_file = Path(__file__).resolve().parents[1] / "Example" / "Raw" / "CDI_12.DNG"
        result = _validate_dng_file(str(input_file))
        self.assertEqual(result, input_file)

    def test_validate_dng_file_rejects_non_dng(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp = Path(f.name)
        try:
            result = _validate_dng_file(str(tmp))
            self.assertIsInstance(result, str)
            self.assertIn("仅支持 .DNG", result)
        finally:
            tmp.unlink(missing_ok=True)

    def test_render_dng_input_reports_invalid_file(self) -> None:
        selected, image, status = render_dng_input(None)
        self.assertIsNone(selected)
        self.assertIsNone(image)
        self.assertIn("选择一个 DNG", status)

    def test_render_dng_input_clears_selection_when_decode_fails(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".DNG", delete=False) as f:
            f.write(b"not a real dng")
            tmp = Path(f.name)
        try:
            selected, image, status = render_dng_input(str(tmp))
            self.assertIsNone(selected)
            self.assertIsNone(image)
            self.assertIn("预览读取失败", status)
        finally:
            tmp.unlink(missing_ok=True)

    def test_cleanup_old_exports_removes_expired_export_dirs(self) -> None:
        class FakeExportDir:
            def __init__(self, name: str, mtime: float, is_directory: bool = True) -> None:
                self.name = name
                self.mtime = mtime
                self.is_directory = is_directory

            def is_dir(self) -> bool:
                return self.is_directory

            def stat(self):
                return type("Stat", (), {"st_mtime": self.mtime})()

        class FakeTempRoot:
            def __init__(self, entries: list[FakeExportDir]) -> None:
                self.entries = entries
                self.pattern = ""

            def glob(self, pattern: str):
                self.pattern = pattern
                return iter(self.entries)

        old_dir = FakeExportDir("caye_export_old", 1000.0)
        keep_dir = FakeExportDir("caye_export_keep", 1000.0 + (24 * 60 * 60))
        non_dir = FakeExportDir("caye_export_file", 1000.0, is_directory=False)
        root = FakeTempRoot([old_dir, keep_dir, non_dir])

        with patch("caye_watermark.webui.shutil.rmtree") as mock_rmtree:
            cleanup_old_exports(now=1000.0 + (25 * 60 * 60), temp_root=root)

        self.assertEqual(root.pattern, "caye_export_*")
        mock_rmtree.assert_called_once_with(old_dir, ignore_errors=True)

    def test_validate_options_rejects_invalid_scale(self) -> None:
        options = ProcessingOptions(
            enable_watermark=False,
            watermark_scale=0.0,
        )
        result = _validate_options(options)
        self.assertIsInstance(result, str)
        self.assertIn("水印尺寸", result)

    def test_validate_options_rejects_invalid_opacity(self) -> None:
        options = ProcessingOptions(
            enable_watermark=False,
            opacity=300,
        )
        result = _validate_options(options)
        self.assertIsInstance(result, str)
        self.assertIn("不透明度", result)


if __name__ == "__main__":
    unittest.main()
