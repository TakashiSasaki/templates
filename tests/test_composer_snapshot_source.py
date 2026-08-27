from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_source


class FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self.data = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self.data if amount < 0 else self.data[:amount]


class SnapshotSourceContextTests(unittest.TestCase):
    def test_snapshot_authority_detects_post_acquisition_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            authority = root / "catalog.json"
            original = b"{}\n"
            authority.write_bytes(original)
            context = composer_source.SnapshotSourceContext(
                root=root,
                repository="TakashiSasaki/templates",
                pinned_revision="1" * 40,
                files={"catalog.json": hashlib.sha256(original).hexdigest()},
            )
            context.assert_authority(authority)
            authority.write_bytes(b'{"changed":true}\n')
            with self.assertRaisesRegex(
                composer_source.SourceContextError,
                "bytes changed after acquisition",
            ) as caught:
                context.assert_authority(authority)
            self.assertEqual(caught.exception.code, "DIRTY_SOURCE")

    def test_snapshot_authority_rejects_parent_symlink_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "source"
            nested = root / "catalog"
            nested.mkdir(parents=True)
            authority = nested / "authority.json"
            original = b"{}\n"
            authority.write_bytes(original)
            context = composer_source.SnapshotSourceContext(
                root=root,
                repository="TakashiSasaki/templates",
                pinned_revision="1" * 40,
                files={
                    "catalog/authority.json": hashlib.sha256(original).hexdigest(),
                },
            )
            context.assert_authority(authority)

            external = base / "external"
            external.mkdir()
            (external / "authority.json").write_bytes(original)
            authority.unlink()
            nested.rmdir()
            try:
                nested.symlink_to(external, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"directory symlinks are unavailable: {exc}")

            with self.assertRaisesRegex(
                composer_source.SourceContextError,
                "parent must remain",
            ) as caught:
                context.assert_authority(root / "catalog" / "authority.json")
            self.assertEqual(caught.exception.code, "INVALID_SOURCE_AUTHORITY")

    def test_context_from_environment_loads_snapshot_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            authority = root / "authority.json"
            data = b"{}\n"
            authority.write_bytes(data)
            metadata = Path(temporary) / "context.json"
            metadata.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "repository": "TakashiSasaki/templates",
                        "revision": "1" * 40,
                        "files": {
                            "authority.json": hashlib.sha256(data).hexdigest(),
                        },
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(
                "os.environ",
                {composer_source.SOURCE_CONTEXT_ENV: str(metadata)},
                clear=False,
            ):
                context = composer_source.context_from_environment(root)
            self.assertIsInstance(context, composer_source.SnapshotSourceContext)
            self.assertEqual(context.revision(), "1" * 40)
            context.assert_authority(authority)

    def test_github_compare_accepts_ahead(self) -> None:
        def opener(_request, *, timeout: int):
            self.assertEqual(timeout, 30)
            return FakeResponse({"status": "ahead"})

        composer_source.verify_github_descendant(
            "TakashiSasaki/templates",
            "1" * 40,
            "2" * 40,
            opener=opener,
        )

    def test_github_compare_rejects_diverged(self) -> None:
        def opener(_request, *, timeout: int):
            self.assertEqual(timeout, 30)
            return FakeResponse({"status": "diverged"})

        with self.assertRaisesRegex(
            composer_source.SourceContextError,
            "not a descendant",
        ) as caught:
            composer_source.verify_github_descendant(
                "TakashiSasaki/templates",
                "1" * 40,
                "2" * 40,
                opener=opener,
            )
        self.assertEqual(caught.exception.code, "SOURCE_REVISION_NOT_DESCENDANT")

    def test_github_compare_404_fails_closed(self) -> None:
        error = urllib.error.HTTPError(
            "https://api.github.invalid/compare",
            404,
            "Not Found",
            {},
            io.BytesIO(),
        )

        def opener(_request, *, timeout: int):
            self.assertEqual(timeout, 30)
            raise error

        with self.assertRaisesRegex(
            composer_source.SourceContextError,
            "unavailable from the canonical GitHub history",
        ) as caught:
            composer_source.verify_github_descendant(
                "TakashiSasaki/templates",
                "1" * 40,
                "2" * 40,
                opener=opener,
            )
        self.assertEqual(caught.exception.code, "OLD_SOURCE_REVISION_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
