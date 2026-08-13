#!/usr/bin/env python3
"""Normalize one UTF-8 file using only the Python standard library."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python scripts/normalize.py INPUT OUTPUT", file=sys.stderr)
        return 2

    input_text, output_text = argv
    input_path = Path(input_text)
    output_path = Path(output_text)

    try:
        if output_path.exists() and os.path.samefile(input_path, output_path):
            print("input and output must refer to different files", file=sys.stderr)
            return 2

        raw = input_path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            print("invalid UTF-8 input", file=sys.stderr)
            return 3

        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[\t ]+(?=\n|$)", "", normalized)
        normalized = normalized.rstrip("\n") + "\n"
        output_path.write_bytes(normalized.encode("utf-8"))
        print(output_text)
        return 0
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
