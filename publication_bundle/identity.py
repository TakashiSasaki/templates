"""Provider identity primitives shared by semantic publication contracts."""
from __future__ import annotations

import re


FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
REPOSITORY = re.compile(r"\A[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")

BIDIRECTIONAL_CONTROLS = frozenset(
    {
        "\u061c", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c",
        "\u202d", "\u202e", "\u2066", "\u2067", "\u2068", "\u2069",
    }
)
