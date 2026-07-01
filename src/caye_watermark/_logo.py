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


def _resource_roots(base_path: Path | None = None) -> list[Path]:
    roots = [Path.cwd()]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))  # type: ignore[attr-defined]
    if base_path is not None:
        roots.append(base_path.parent)
    return roots


def resolve_preset_logo(filename: str, base_path: Path | None = None) -> Path | None:
    for root in _resource_roots(base_path):
        for candidate in (
            root / "Example" / "Brands" / filename,
            root / filename,
        ):
            resolved = candidate.resolve()
            if resolved.exists():
                return resolved
    return None


def find_default_logo(base_path: Path | None = None) -> Path | None:
    candidates = []
    for root in _resource_roots(base_path):
        candidates.extend([
            root / "Example" / "Brands" / "CAYE.webp",
            root / "Example" / "Brands" / "CAYE.png",
            root / "Example" / "Brands" / "Laiye.png",
            root / "CAYE.webp",
            root / "CAYE.png",
            root / "Laiye.png",
        ])

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen and resolved.exists():
            return resolved
        seen.add(resolved)
    return None
