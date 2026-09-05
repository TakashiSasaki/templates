from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.generate_repository_browser import (
    FileRecord,
    RepositoryBrowserError,
    write_verified_file_page,
)


REVISION = "a" * 40


def record() -> FileRecord:
    return FileRecord(
        path=b"README.md",
        object_id="b" * 40,
        size=6,
        viewer_url="content/test.html",
        source_url=f"https://github.com/example/repository/blob/{REVISION}/README.md",
        viewable=True,
        reason=None,
        text="line\n",
    )


class RepositoryBrowserPostWriteValidationTests(unittest.TestCase):
    def test_verified_writer_preserves_validated_line_anchor_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "viewer.html"
            write_verified_file_page(destination, "site", REVISION, record())
            on_disk = destination.read_text(encoding="utf-8")

        self.assertIn('id="L1"', on_disk)
        self.assertIn('href="#L1"', on_disk)

    def test_verified_writer_rejects_corrupted_line_anchor_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "viewer.html"
            original_write_text = Path.write_text

            def corrupt_write(
                path: Path,
                data: str,
                *args: object,
                **kwargs: object,
            ) -> int:
                if path == destination:
                    data = data.replace('id="L1"', 'id="BROKEN"', 1)
                return original_write_text(path, data, *args, **kwargs)

            with mock.patch.object(Path, "write_text", new=corrupt_write):
                with self.assertRaisesRegex(
                    RepositoryBrowserError,
                    "repository viewer post-write verification failed",
                ):
                    write_verified_file_page(
                        destination,
                        "site",
                        REVISION,
                        record(),
                    )


if __name__ == "__main__":
    unittest.main()
