from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from caye_watermark.cli import build_output_path
from caye_watermark.pipeline import (
    EdgeCropAnalysis,
    get_restoration_settings,
    optimize_image,
    repair_abnormal_edges,
)


class CliRegressionTests(unittest.TestCase):
    def test_build_output_path_uses_review_suffix_without_watermark(self) -> None:
        path = build_output_path(Path("/tmp/CDI_12.DNG"), None, enable_watermark=False)
        self.assertEqual(path.name, "CDI_12_review.png")

    def test_build_output_path_uses_watermarked_suffix_with_watermark(self) -> None:
        path = build_output_path(Path("/tmp/CDI_12.DNG"), None, enable_watermark=True)
        self.assertEqual(path.name, "CDI_12_watermarked.png")


class PipelineRegressionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
