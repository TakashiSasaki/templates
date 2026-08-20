from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from composer_cli_messages import consumer_message, remediate_payload  # noqa: E402


class ComposerCliUnknownDiagnosticTests(unittest.TestCase):
    def test_consumer_message_preserves_unknown_message_exactly(self) -> None:
        message = "\t opaque future diagnostic with surrounding whitespace \n"
        entry = {
            "code": "FUTURE_DIAGNOSTIC_CODE",
            "message": message,
            "detail": {"preserve": [1, 2, 3]},
        }

        self.assertEqual(consumer_message(entry), message)

    def test_payload_remediation_preserves_unknown_diagnostics_in_all_views(self) -> None:
        top_message = "  future top-level diagnostic  \n"
        conflict_message = "\tfuture conflict diagnostic\t"
        file_conflict_message = "\nfuture file-conflict diagnostic\n"
        source = {
            "status": "conflict",
            "code": "FUTURE_TOP_LEVEL_CODE",
            "message": top_message,
            "metadata": {"opaque": True},
            "conflicts": [
                {
                    "code": "FUTURE_CONFLICT_CODE",
                    "message": conflict_message,
                    "destination": "future.txt",
                    "extra": ["leave", "unchanged"],
                },
                {
                    "code": "LOCAL_MODIFICATION",
                    "message": "internal known diagnostic",
                    "destination": "managed.txt",
                    "ownership": "managed",
                },
            ],
            "files": {
                "conflict": [
                    {
                        "code": "FUTURE_FILE_CONFLICT_CODE",
                        "message": file_conflict_message,
                        "destination": "future-file.txt",
                        "extra": {"leave": "unchanged"},
                    }
                ]
            },
        }
        original = copy.deepcopy(source)

        result = remediate_payload(source)

        self.assertEqual(result["code"], "FUTURE_TOP_LEVEL_CODE")
        self.assertEqual(result["message"], top_message)
        self.assertEqual(result["metadata"], {"opaque": True})
        self.assertEqual(result["conflicts"][0], original["conflicts"][0])
        self.assertEqual(result["files"]["conflict"][0], original["files"]["conflict"][0])
        self.assertEqual(result["conflicts"][1]["code"], "LOCAL_MODIFICATION")
        self.assertIn("will not merge, overwrite, or delete", result["conflicts"][1]["message"])
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
