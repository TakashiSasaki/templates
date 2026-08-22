from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.generate_index_navigation import (
    IndexNavigationError,
    checked_revision,
    normalize_link_description,
    parse_index,
)


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "TakashiSasaki/templates"
PROVIDER_ORDER = ("composition", "policy")
POLICY_LAYER_INDEXES = {
    "docs/provider/index.md",
    "docs/shared-policy/index.md",
    "docs/consumer/index.md",
}


def checked_out_providers(test_case: unittest.TestCase) -> dict[str, Path]:
    providers = {name: ROOT.parent / f"{name}-source" for name in PROVIDER_ORDER}
    missing = [name for name, path in providers.items() if not path.is_dir()]
    if missing:
        test_case.skipTest(
            "provider checkouts are not available outside the Pages CI layout: "
            + ", ".join(missing)
        )
    return providers


def run_navigation(
    command_name: str,
    providers: dict[str, Path],
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_composition_navigation.py"),
        command_name,
        *arguments,
    ]
    for name in PROVIDER_ORDER:
        command.extend(["--provider", f"{name}={providers[name]}"])
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class InlineCodeDescriptionTests(unittest.TestCase):
    def test_code_spans_are_rendered_as_literal_description_text(self) -> None:
        parsed = parse_index(
            "# Root\n\n"
            "* [Document](document.md) - Defines the copyable `template/` boundary and `agent-policy` command.\n",
            "docs/index.md",
        )
        self.assertEqual(
            parsed.links[0].description,
            "Defines the copyable template/ boundary and agent-policy command.",
        )

    def test_markdown_like_text_inside_code_spans_remains_literal(self) -> None:
        description = normalize_link_description(
            "Literal `*not emphasis* [x](y) <https://example.invalid> <b>` text",
            "docs/index.md",
            3,
        )
        self.assertEqual(
            description,
            "Literal *not emphasis* [x](y) <https://example.invalid> <b> text",
        )

    def test_backslash_escapes_and_entities_are_not_decoded_inside_code_spans(self) -> None:
        description = normalize_link_description(
            r"Outside \* &amp; and code `\* &amp;`",
            "docs/index.md",
            3,
        )
        self.assertEqual(description, r"Outside * & and code \* &amp;")

    def test_richer_markdown_outside_code_spans_still_fails_closed(self) -> None:
        descriptions = (
            "Outside *emphasis* and `code`",
            "Outside [link](target.md) and `code`",
            "Outside <https://example.invalid> and `code`",
            "Outside <b>raw</b> and `code`",
        )
        for description in descriptions:
            with self.subTest(description=description):
                with self.assertRaises(IndexNavigationError):
                    normalize_link_description(description, "docs/index.md", 3)

    def test_code_span_matching_is_sequential_and_non_overlapping(self) -> None:
        with self.assertRaisesRegex(IndexNavigationError, "unsupported emphasis"):
            normalize_link_description(
                "`safe `` code` *emphasis* ``",
                "docs/index.md",
                3,
            )

    def test_richer_constructs_cannot_be_hidden_by_later_backticks(self) -> None:
        descriptions = (
            "[x](foo`bar) tail`",
            "<https://x/`y> tail`",
            '<a title="`y"> tail`',
        )
        for description in descriptions:
            with self.subTest(description=description):
                with self.assertRaises(IndexNavigationError):
                    normalize_link_description(description, "docs/index.md", 3)

    def test_code_span_precedence_keeps_apparent_emphasis_closer_literal(self) -> None:
        self.assertEqual(
            normalize_link_description(
                "*em`phasis* tail`",
                "docs/index.md",
                3,
            ),
            "*emphasis* tail",
        )


class LockedProviderGraphTests(unittest.TestCase):
    def test_checked_out_provider_revisions_generate_graph_end_to_end(self) -> None:
        providers = checked_out_providers(self)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "graph.json"
            result = run_navigation(
                "graph",
                providers,
                "--repository",
                REPOSITORY,
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            graph = json.loads(output.read_text(encoding="utf-8"))

        by_name = {provider["name"]: provider for provider in graph["providers"]}

        self.assertEqual(tuple(by_name), PROVIDER_ORDER)
        for name in PROVIDER_ORDER:
            with self.subTest(provider=name):
                provider = by_name[name]
                self.assertEqual(provider["revision"], checked_revision(providers[name]))
                self.assertEqual(provider["root_index"], "docs/index.md")
                self.assertTrue(provider["indexes"])
                self.assertTrue(provider["edges"])
                self.assertIn(
                    "docs/index.md",
                    {index["path"] for index in provider["indexes"]},
                )

        policy_indexes = {index["path"] for index in by_name["policy"]["indexes"]}
        self.assertTrue(POLICY_LAYER_INDEXES.issubset(policy_indexes))

        root_index = (providers["policy"] / "docs" / "index.md").read_text(
            encoding="utf-8"
        )
        overview = (providers["policy"] / "docs" / "overview.md").read_text(
            encoding="utf-8"
        )
        layer_targets = {
            "provider/index.md": providers["policy"] / "docs" / "provider" / "index.md",
            "shared-policy/index.md": providers["policy"] / "docs" / "shared-policy" / "index.md",
            "consumer/index.md": providers["policy"] / "docs" / "consumer" / "index.md",
        }
        for target, path in layer_targets.items():
            with self.subTest(policy_root_target=target):
                self.assertIn(f"]({target})", root_index)
                self.assertTrue(path.is_file())
            with self.subTest(policy_overview_target=target):
                self.assertIn(f"]({target})", overview)

    def test_checked_out_composition_translation_generates_guided_overlay(self) -> None:
        providers = checked_out_providers(self)

        with tempfile.TemporaryDirectory() as directory:
            graph_path = Path(directory) / "graph.json"
            locale_path = Path(directory) / "locales.json"
            graph_result = run_navigation(
                "graph",
                providers,
                "--repository",
                REPOSITORY,
                "--output",
                str(graph_path),
            )
            self.assertEqual(
                graph_result.returncode,
                0,
                graph_result.stdout + graph_result.stderr,
            )
            locale_result = run_navigation(
                "locales",
                providers,
                "--graph",
                str(graph_path),
                "--output",
                str(locale_path),
            )
            self.assertEqual(
                locale_result.returncode,
                0,
                locale_result.stdout + locale_result.stderr,
            )
            payload = json.loads(locale_path.read_text(encoding="utf-8"))

        japanese = next(locale for locale in payload["locales"] if locale["language"] == "ja")
        composition = next(
            provider
            for provider in japanese["providers"]
            if provider["name"] == "composition"
        )
        overlay = next(
            index for index in composition["indexes"] if index["path"] == "docs/index.md"
        )
        self.assertEqual(composition["revision"], checked_revision(providers["composition"]))
        self.assertEqual(overlay["title"], "Composition ドキュメント索引")
        self.assertEqual(overlay["sections"][0]["title"], "ここから始める")
        self.assertEqual(overlay["links"][0]["label"], "Composition の利用方法")
        self.assertNotIn("target", overlay["links"][0])
        self.assertNotIn("raw_target", overlay["links"][0])


if __name__ == "__main__":
    unittest.main()
