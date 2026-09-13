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
