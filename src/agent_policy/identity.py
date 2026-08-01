from __future__ import annotations

import re

TOOLCHAIN_REPOSITORY = "TakashiSasaki/templates"
TOOLCHAIN_BRANCH = "policy"
LOCAL_DEVELOPMENT_REVISION = "LOCAL-DEVELOPMENT"
FULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def toolchain_reference(
    revision: str,
    *,
    allow_local_development: bool = True,
) -> dict[str, str]:
    valid = FULL_COMMIT_SHA.fullmatch(revision) is not None
    if allow_local_development and revision == LOCAL_DEVELOPMENT_REVISION:
        valid = True
    if not valid:
        raise ValueError("Toolchain revision must be a full lowercase commit SHA")
    return {
        "repository": TOOLCHAIN_REPOSITORY,
        "revision": revision,
    }
