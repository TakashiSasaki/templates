"""Caller-visible text-stat CLI."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import BinaryIO, TextIO

from . import CONTRACT_VERSION, VERSION

USAGE = "Usage: text-stat [--output human|json] INPUT"
ASCII_NON_WHITESPACE = re.compile(r"[^ \t\r\n\f\v]+")


def analyze(raw: bytes, text: str) -> dict[str, int]:
    line_count = 0 if not text else text.count("\n") + (0 if text.endswith("\n") else 1)
    return {
        "bytes": len(raw),
        "lines": line_count,
        "words": len(ASCII_NON_WHITESPACE.findall(text)),
    }


def _write(stdout: TextIO, stderr: TextIO, text: str) -> int:
    try:
        stdout.write(text)
        stdout.flush()
        return 0
    except (OSError, ValueError) as exc:
        try:
            stderr.write(f"unable to write output: {exc}\n")
            stderr.flush()
        except (OSError, ValueError):
            pass
        return 5


def _error(stderr: TextIO, message: str, status: int) -> int:
    try:
        stderr.write(message + "\n")
        stderr.flush()
        return status
    except (OSError, ValueError):
        return 5


def _help_text() -> str:
    return (
        f"{USAGE}\n"
        "    --output FORMAT              Select human or JSON output\n"
        "    --version                    Print the package version\n"
        "    -h, --help                   Show this help\n"
    )


def run(
    argv: list[str],
    *,
    stdin: BinaryIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdin = stdin if stdin is not None else sys.stdin.buffer
    stdout = stdout if stdout is not None else sys.stdout
    stderr = stderr if stderr is not None else sys.stderr

    output = "human"
    operands: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--version":
            return _write(stdout, stderr, VERSION + "\n")
        if token in {"-h", "--help"}:
            return _write(stdout, stderr, _help_text())
        if token == "--output":
            if index + 1 >= len(argv):
                return _error(stderr, "missing argument: --output", 2)
            output = argv[index + 1]
            if output not in {"human", "json"}:
                return _error(
                    stderr,
                    f"invalid argument: --output {output}",
                    2,
                )
            index += 2
            continue
        if token.startswith("--output="):
            output = token.split("=", 1)[1]
            if output not in {"human", "json"}:
                return _error(
                    stderr,
                    f"invalid argument: --output={output}",
                    2,
                )
            index += 1
            continue
        if token.startswith("-") and token != "-":
            return _error(stderr, f"invalid option: {token}", 2)
        operands.append(token)
        index += 1

    if len(operands) != 1:
        return _error(stderr, "exactly one INPUT path or - is required", 2)

    try:
        if operands[0] == "-":
            raw = stdin.read()
        else:
            raw = Path(operands[0]).read_bytes()
    except (OSError, ValueError) as exc:
        return _error(stderr, f"unable to read input: {exc}", 3)

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _error(stderr, "input is not valid UTF-8", 2)

    result = analyze(raw, text)
    if output == "json":
        payload = json.dumps(
            {
                "contractVersion": CONTRACT_VERSION,
                "ok": True,
                "result": result,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return _write(stdout, stderr, payload + "\n")

    return _write(
        stdout,
        stderr,
        f"bytes: {result['bytes']}\nlines: {result['lines']}\nwords: {result['words']}\n",
    )


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
