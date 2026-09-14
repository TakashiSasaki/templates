"""Select the same publication mapping as the compatibility build under test.

Pristine repository fixtures still use their own ROOT. Provider-dependent
publication integration tests use this root, which the workflow sets only after
successfully staging a disposable copy. An invalid explicit root never falls back.
"""

import os
from pathlib import Path


def publication_root(pristine_root: Path) -> Path:
    selected = os.environ.get("SITE_PUBLICATION_ROOT")
    if selected is None:
        return pristine_root
    if not selected:
        raise ValueError("SITE_PUBLICATION_ROOT must not be empty")
    root = Path(selected).resolve(strict=True)
    if not (root / "site-manifest.json").is_file():
        raise ValueError("SITE_PUBLICATION_ROOT must contain site-manifest.json")
    return root


def provider_root(name: str, site_root: Path) -> Path:
    """Resolve an explicit preflight provider checkout without weakening CI defaults."""
    variable = f"SITE_{name.upper()}_ROOT"
    selected = os.environ.get(variable)
    if selected is None:
        return site_root.parent / f"{name}-source"
    if not selected:
        raise ValueError(f"{variable} must not be empty")
    root = Path(selected).resolve(strict=True)
    if not (root / "docs/publication-catalog.json").is_file():
        raise ValueError(f"{variable} must contain a provider publication catalog")
    return root
