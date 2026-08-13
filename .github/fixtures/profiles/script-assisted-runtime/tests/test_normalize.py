#!/usr/bin/env python3
"""Executable tests for the private line-normalization helper."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
HELPER = SKILL_ROOT / "scripts/normalize.py"


def run_helper(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), *args],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="normalize-helper-test") as temporary:
        directory = Path(temporary)
        input_path = directory / "input.txt"
        output_path = directory / "output.txt"
        input_path.write_bytes(b"alpha  \r\nbeta\t\r\n")
        input_before = input_path.read_bytes()

        result = run_helper(str(input_path), str(output_path))
        if not (
            result.returncode == 0
            and result.stdout.rstrip("\r\n") == str(output_path)
            and result.stderr == ""
            and output_path.read_bytes() == b"alpha\nbeta\n"
            and input_path.read_bytes() == input_before
        ):
            failures.append(
                "normalization failed: "
                f"status={result.returncode!r}, stdout={result.stdout!r}, "
                f"stderr={result.stderr!r}"
            )

        result = run_helper(str(input_path), str(input_path))
        if not (
            result.returncode == 2
            and result.stdout == ""
            and result.stderr.strip()
            == "input and output must refer to different files"
            and input_path.read_bytes() == input_before
        ):
            failures.append(
                "same-file rejection failed: "
                f"status={result.returncode!r}, stdout={result.stdout!r}, "
                f"stderr={result.stderr!r}"
            )

        hardlink_path = directory / "hardlink.txt"
        try:
            os.link(input_path, hardlink_path)
        except OSError as exc:
            failures.append(f"could not create hard-link regression fixture: {exc}")
        else:
            result = run_helper(str(input_path), str(hardlink_path))
            if not (
                result.returncode == 2
                and result.stdout == ""
                and result.stderr.strip()
                == "input and output must refer to different files"
                and input_path.read_bytes() == input_before
            ):
                failures.append(
                    "hard-link rejection failed: "
                    f"status={result.returncode!r}, stdout={result.stdout!r}, "
                    f"stderr={result.stderr!r}"
                )

        invalid_path = directory / "invalid.txt"
        invalid_output_path = directory / "invalid-output.txt"
        invalid_path.write_bytes(b"\xff")
        result = run_helper(str(invalid_path), str(invalid_output_path))
        if not (
            result.returncode == 3
            and result.stdout == ""
            and result.stderr.strip() == "invalid UTF-8 input"
            and not invalid_output_path.exists()
        ):
            failures.append(
                "invalid UTF-8 rejection failed: "
                f"status={result.returncode!r}, stdout={result.stdout!r}, "
                f"stderr={result.stderr!r}"
            )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Line normalization helper tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
