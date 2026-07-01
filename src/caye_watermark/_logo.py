from __future__ import annotations

import sys
from pathlib import Path

PRESET_LOGO_FILENAMES = (
    "CAYE.webp",
    "HACHIMITSU.png",
    "LaiyeRed.png",
    "LaiyeWhite.png",
)
CUSTOM_LOGO_CHOICE = "自选"
LOGO_CHOICES = (*PRESET_LOGO_FILENAMES, CUSTOM_LOGO_CHOICE)
PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_BRANDS_DIR = PACKAGE_ROOT / "assets" / "brands"


def _resource_roots(base_path: Path | None = None) -> list[Path]:
    roots = [PACKAGE_ROOT, Path.cwd()]
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))  # type: ignore[attr-defined]
    if base_path is not None:
        roots.append(base_path.parent)
    return roots


def _brand_asset_candidates(root: Path, filename: str) -> tuple[Path, ...]:
    return (
        root / "assets" / "brands" / filename,
        root / "caye_watermark" / "assets" / "brands" / filename,
        root / "Example" / "Brands" / filename,
        root / filename,
    )


def resolve_preset_logo(filename: str, base_path: Path | None = None) -> Path | None:
    for root in _resource_roots(base_path):
        for candidate in _brand_asset_candidates(root, filename):
            resolved = candidate.resolve()
            if resolved.exists():
                return resolved
    return None


def find_default_logo(base_path: Path | None = None) -> Path | None:
    candidates = []
    for root in _resource_roots(base_path):
        candidates.extend(
            _brand_asset_candidates(root, "CAYE.webp")
            + _brand_asset_candidates(root, "CAYE.png")
            + _brand_asset_candidates(root, "Laiye.png")
        )

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen and resolved.exists():
            return resolved
        seen.add(resolved)
    return None
