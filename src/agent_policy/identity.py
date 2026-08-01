from __future__ import annotations

import re

TOOLCHAIN_REPOSITORY = "TakashiSasaki/templates"
TOOLCHAIN_BRANCH = "policy"
LOCAL_DEVELOPMENT_REVISION = "LOCAL-DEVELOPMENT"
FULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def toolchain_reference(revision: str) -> dict[str, str]:
    return {
        "repository": TOOLCHAIN_REPOSITORY,
        "revision": revision,
    }


def immutable_toolchain_reference(revision: str) -> dict[str, str]:
    if FULL_COMMIT_SHA.fullmatch(revision) is None:
        raise ValueError("Toolchain revision must be a full lowercase commit SHA")
    return toolchain_reference(revision)
