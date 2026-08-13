#!/usr/bin/env python3
"""Unit tests for the text-stat CLI contract."""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from text_stat.cli import analyze, run  # noqa: E402


class BrokenTextIO(io.StringIO):
    def __init__(self, *, fail_write: bool = False, fail_flush: bool = False) -> None:
        super().__init__()
        self.fail_write = fail_write
        self.fail_flush = fail_flush

    def write(self, value: str) -> int:
        if self.fail_write:
            raise OSError("injected write failure")
        return super().write(value)

    def flush(self) -> None:
        if self.fail_flush:
            raise OSError("injected flush failure")
        super().flush()


class TextStatTests(unittest.TestCase):
    def invoke(
        self,
        argv: list[str],
        *,
        stdin_bytes: bytes = b"",
        stdout: io.StringIO | None = None,
        stderr: io.StringIO | None = None,
    ) -> tuple[int, io.StringIO, io.StringIO]:
        out = stdout or io.StringIO()
        err = stderr or io.StringIO()
        status = run(
            argv,
            stdin=io.BytesIO(stdin_bytes),
            stdout=out,
            stderr=err,
        )
        return status, out, err

    def test_help(self) -> None:
        status, out, err = self.invoke(["--help"])
        self.assertEqual(0, status)
        self.assertIn("Usage: text-stat", out.getvalue())
        self.assertEqual("", err.getvalue())

    def test_version(self) -> None:
        status, out, err = self.invoke(["--version"])
        self.assertEqual(0, status)
        self.assertEqual("1.0.0\n", out.getvalue())
        self.assertEqual("", err.getvalue())

    def test_human_stdin_and_binary_crlf_count(self) -> None:
        status, out, err = self.invoke(["-"], stdin_bytes=b"one\r\ntwo\r\n")
        self.assertEqual(0, status)
        self.assertEqual("bytes: 10\nlines: 2\nwords: 2\n", out.getvalue())
        self.assertEqual("", err.getvalue())

    def test_json_contract(self) -> None:
        status, out, err = self.invoke(
            ["--output", "json", "-"], stdin_bytes="one two\n".encode()
        )
        self.assertEqual(0, status)
        payload = json.loads(out.getvalue())
        self.assertEqual("1", payload["contractVersion"])
        self.assertIs(True, payload["ok"])
        self.assertEqual({"bytes": 8, "lines": 1, "words": 2}, payload["result"])
        self.assertEqual("", err.getvalue())

    def test_ascii_whitespace_word_semantics(self) -> None:
        raw = "a\u00a0b c".encode("utf-8")
        self.assertEqual(2, analyze(raw, raw.decode("utf-8"))["words"])

    def test_invalid_option(self) -> None:
        status, out, err = self.invoke(["--unknown"])
        self.assertEqual(2, status)
        self.assertEqual("", out.getvalue())
        self.assertIn("invalid option", err.getvalue())

    def test_missing_operand(self) -> None:
        status, out, err = self.invoke([])
        self.assertEqual(2, status)
        self.assertEqual("", out.getvalue())
        self.assertEqual("exactly one INPUT path or - is required\n", err.getvalue())

    def test_invalid_utf8(self) -> None:
        status, out, err = self.invoke(["-"], stdin_bytes=b"\xff")
        self.assertEqual(2, status)
        self.assertEqual("", out.getvalue())
        self.assertEqual("input is not valid UTF-8\n", err.getvalue())

    def test_missing_file(self) -> None:
        status, out, err = self.invoke(["definitely-missing.txt"])
        self.assertEqual(3, status)
        self.assertEqual("", out.getvalue())
        self.assertIn("unable to read input:", err.getvalue())

    def test_stdout_write_failure(self) -> None:
        out = BrokenTextIO(fail_write=True)
        status, _, err = self.invoke(["--version"], stdout=out)
        self.assertEqual(5, status)
        self.assertIn("unable to write output:", err.getvalue())

    def test_stdout_flush_failure(self) -> None:
        out = BrokenTextIO(fail_flush=True)
        status, _, err = self.invoke(["--version"], stdout=out)
        self.assertEqual(5, status)
        self.assertIn("unable to write output:", err.getvalue())

    def test_diagnostic_failure_maps_to_output_io_status(self) -> None:
        err = BrokenTextIO(fail_write=True)
        status, out, _ = self.invoke(["--unknown"], stderr=err)
        self.assertEqual(5, status)
        self.assertEqual("", out.getvalue())


if __name__ == "__main__":
    unittest.main()
