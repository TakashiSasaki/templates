"""Immutable Git tree parsing primitives for provider index navigation."""
from __future__ import annotations

import re
from dataclasses import dataclass


FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
REPOSITORY = re.compile(r"\A[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")

BIDIRECTIONAL_CONTROLS = frozenset(
    {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)


class RepositoryInputError(RuntimeError):
    """Raised when an immutable provider Git tree cannot be parsed safely."""


@dataclass
class TreeEntry:
    path: bytes
    mode: str
    kind: str
    object_id: str


def parse_ls_tree(raw: bytes) -> list[TreeEntry]:
    result: list[TreeEntry] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path = record.split(b"\t", maxsplit=1)
            mode, kind, object_id = metadata.decode("ascii").split(" ", maxsplit=2)
        except (ValueError, UnicodeDecodeError) as exc:
            raise RepositoryInputError("git ls-tree returned malformed output") from exc
        if not path or path.startswith(b"/") or b"\0" in path:
            raise RepositoryInputError("git ls-tree returned an unsafe path")
        result.append(
            TreeEntry(path=path, mode=mode, kind=kind, object_id=object_id)
        )
    return result
