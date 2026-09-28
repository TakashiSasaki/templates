"""Offline integrity checks for an informative study, not OKF conformance tests."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/studies/open-knowledge-format"
BASELINE = STUDY / "observation-2026-09-28.json"


def check_source_pins(data: dict) -> None:
    revision = data["revision"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("observation must pin a full Git revision")
    ids = set()
    for source in data["sources"]:
        if source["id"] in ids:
            raise ValueError("duplicate source id")
        ids.add(source["id"])
        if not re.fullmatch(r"[0-9a-f]{40}", source["blob"]):
            raise ValueError("missing full blob identity")
        expected = f"https://github.com/{data['upstreamRepository']}/blob/{revision}/{source['path']}"
        if source["url"] != expected:
            raise ValueError("source URL disagrees with observation revision/path")


def prose(text: str) -> str:
    """Ignore illustrative fenced code when checking actual document links."""
    lines = []
    fence = None
    for line in text.splitlines():
        found = re.match(r"^\s*(`{3,}|~{3,})", line)
        if found:
            marker = found.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return "\n".join(lines)


def check_local_links(path: Path, text: str) -> None:
    for match in re.finditer(r"\[[^\]\n]*\]\(([^)\n]+)\)", prose(text)):
        parsed = urlsplit(match.group(1))
        if parsed.scheme or parsed.netloc:
            continue
        target = path.parent / unquote(parsed.path) if parsed.path else path
        if not target.is_file():
            raise ValueError(f"missing local study target: {match.group(1)}")
        if parsed.fragment:
            body = target.read_text(encoding="utf-8")
            anchor = unquote(parsed.fragment)
            if f'id="{anchor}"' not in body:
                raise ValueError(f"missing explicit study anchor: {match.group(1)}")


class OKFStudyIntegrityTests(unittest.TestCase):
    def test_source_pins_are_explicit_and_consistent(self):
        check_source_pins(json.loads(BASELINE.read_text(encoding="utf-8")))

    def test_bad_pin_and_mutable_reference_are_rejected(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        for key, value in (("blob", "main"), ("url", "https://github.com/example/main")):
            data = copy.deepcopy(baseline)
            data["sources"][0][key] = value
            with self.assertRaises(ValueError):
                check_source_pins(data)

    def test_question_gap_and_probe_identifiers_remain_addressable(self):
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        questions = (STUDY / "questions.md").read_text(encoding="utf-8")
        self.assertEqual(data["questionIds"], [f"Q{i:02}" for i in range(1, 19)])
        for key in data["questionIds"]:
            self.assertIn(f'id="{key.lower()}"', questions)
        gaps = (STUDY / "implementation-gaps.md").read_text(encoding="utf-8")
        for key in data["gapIds"]:
            self.assertIn(f"| {key} |", gaps)
        self.assertEqual([p["id"] for p in data["probes"]], [f"P{i:02}" for i in range(1, 9)])

    def test_proposals_are_not_represented_as_normative_decisions(self):
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(data["kind"], "informative-okf-study-observation")
        self.assertTrue(all(d["normative"] is False for d in data["discussions"]))
        self.assertFalse(data["probeMethod"]["upstreamSuiteRun"])
        self.assertFalse(data["probeMethod"]["networkUsed"])
        self.assertFalse(data["probeMethod"]["modelUsed"])

    def test_study_links_resolve_without_network(self):
        for path in STUDY.glob("*.md"):
            with self.subTest(path=path.name):
                check_local_links(path, path.read_text(encoding="utf-8"))

    def test_missing_link_is_detected_but_code_example_is_not_a_link(self):
        path = STUDY / "README.md"
        with self.assertRaises(ValueError):
            check_local_links(path, "[missing](does-not-exist.md)")
        check_local_links(path, "```markdown\n[example](does-not-exist.md)\n```\n")

    def test_all_study_files_are_declared_and_indexed(self):
        data = json.loads((ROOT / ".progressive-discovery.json").read_text(encoding="utf-8"))
        declared = set(data["expected_documents"])
        index = (STUDY / "index.md").read_text(encoding="utf-8")
        for path in STUDY.iterdir():
            if not path.is_file():
                continue
            with self.subTest(path=path.name):
                self.assertIn(path.relative_to(ROOT).as_posix(), declared)
                if path.name != "index.md":
                    self.assertIn(f"]({path.name})", index)
        self.assertIn("studies/open-knowledge-format/index.md", (ROOT / "docs/index.md").read_text())

    def test_optional_probe_refuses_wrong_source_before_execution(self):
        # An empty source directory cannot be treated as a successful replay.
        spec = importlib.util.spec_from_file_location("okf_study_probe", STUDY / "probe_reference.py")
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises((OSError, ValueError, KeyError)):
            module.observe(STUDY, {})
        self.assertEqual(module.blob_oid(b"hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a")


if __name__ == "__main__":
    unittest.main()
