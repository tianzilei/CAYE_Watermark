from __future__ import annotations

from pathlib import Path


def find_default_logo(base_path: Path | None = None) -> Path | None:
    search_roots = [Path.cwd()]
    if base_path is not None:
        search_roots.append(base_path.parent)

    candidates = []
    for root in search_roots:
        candidates.extend([
            root / "Example" / "Brands" / "CAYE.png",
            root / "Example" / "Brands" / "CAYE.webp",
            root / "Example" / "Brands" / "Laiye.png",
            root / "CAYE.png",
            root / "CAYE.webp",
            root / "Laiye.png",
        ])

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen and resolved.exists():
            return resolved
        seen.add(resolved)
    return None
