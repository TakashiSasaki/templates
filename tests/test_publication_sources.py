from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from scripts.resolve_publication_sources import (
    SourceLockError,
    render_source_lock,
    resolve_sources,
    write_outputs,
)


class PublicationSourceLockTests(unittest.TestCase):
    def write_lock(self, root: Path, payload: object) -> Path:
        path = root / "publication-sources.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def valid_payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "repository": "TakashiSasaki/templates",
            "publications": {
                "composition": {"revision": "1" * 40},
                "policy": {"revision": "2" * 40},
            },
        }

    def test_resolves_locked_commits_and_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = resolve_sources(
                self.write_lock(root, self.valid_payload()),
                {"policy": "agent/policy-preview"},
            )
            self.assertEqual("1" * 40, resolved["composition"])
            self.assertEqual("agent/policy-preview", resolved["policy"])
            output = StringIO()
            write_outputs(output, resolved)
            self.assertEqual(
                [
                    f"composition={'1' * 40}",
                    "policy=agent/policy-preview",
                ],
                output.getvalue().splitlines(),
            )

    def test_renderer_round_trips_canonical_locked_revisions(self) -> None:
        revisions = {"composition": "1" * 40, "policy": "2" * 40}
        rendered = render_source_lock(revisions)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "publication-sources.json"
            path.write_bytes(rendered)
            self.assertEqual(resolve_sources(path, {}), revisions)
        value = json.loads(rendered)
        self.assertEqual(value["schema_version"], 1)
        self.assertEqual(value["repository"], "TakashiSasaki/templates")
        self.assertEqual(list(value["publications"]), ["composition", "policy"])
        self.assertTrue(rendered.endswith(b"\n"))

    def test_renderer_rejects_invalid_provider_set_and_revision(self) -> None:
        with self.assertRaisesRegex(SourceLockError, "define exactly"):
            render_source_lock({"composition": "1" * 40})
        with self.assertRaisesRegex(SourceLockError, "full lowercase"):
            render_source_lock(
                {"composition": "not-a-sha", "policy": "2" * 40}
            )

    def test_boolean_schema_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self.valid_payload()
            payload["schema_version"] = True
            with self.assertRaisesRegex(SourceLockError, "integer 1"):
                resolve_sources(self.write_lock(root, payload), {})

    def test_non_full_locked_revision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self.valid_payload()
            publications = payload["publications"]
            assert isinstance(publications, dict)
            publications["composition"] = {"revision": "composition"}
            with self.assertRaisesRegex(SourceLockError, "full lowercase"):
                resolve_sources(self.write_lock(root, payload), {})

    def test_legacy_provider_set_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self.valid_payload()
            publications = payload["publications"]
            assert isinstance(publications, dict)
            publications["skill"] = {"revision": "3" * 40}
            with self.assertRaisesRegex(SourceLockError, "exactly"):
                resolve_sources(self.write_lock(root, payload), {})

    def test_duplicate_json_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "publication-sources.json"
            path.write_text(
                '{"schema_version":1,"schema_version":1}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SourceLockError, "duplicate object member"):
                resolve_sources(path, {})


if __name__ == "__main__":
    unittest.main()
