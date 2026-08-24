from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
INSTALLER_RELEASE = ROOT / "release" / "skill-installer.json"


class ConsumerReadmeEntrypointTests(unittest.TestCase):
    def test_consumer_quick_start_precedes_branch_maintenance_details(self) -> None:
        text = README.read_text(encoding="utf-8")
        start = text.index("## Start here: adopt Policy in a product repository")
        authority = text.index("## Authority and branch role")
        development = text.index("## Development")
        self.assertLess(start, authority)
        self.assertLess(authority, development)

    def test_quick_start_exposes_supported_consumer_flow(self) -> None:
        text = README.read_text(encoding="utf-8")
        quick_start = text.split("## Authority and branch role", 1)[0]
        for required in (
            "python scripts/bootstrap.py",
            "--repository /path/to/product-repository",
            "unmanaged-empty",
            "unmanaged-existing",
            "managed",
            "inconsistent",
            "python scripts/run.py --repository /path/to/product-repository validate",
            "python scripts/run.py --repository /path/to/product-repository render",
            "python scripts/run.py --repository /path/to/product-repository check",
            ".agent-policy.yml",
            "docs/getting-started.md",
            "docs/managed-operation.md",
        ):
            self.assertIn(required, quick_start)

    def test_quick_start_installer_is_the_published_immutable_revision(self) -> None:
        release = json.loads(INSTALLER_RELEASE.read_text(encoding="utf-8"))
        revision = release["installer"]["revision"]
        path = release["installer"]["path"]
        quick_start = README.read_text(encoding="utf-8").split(
            "## Authority and branch role", 1
        )[0]
        self.assertIn(
            f"https://raw.githubusercontent.com/TakashiSasaki/templates/{revision}/{path}",
            quick_start,
        )
        self.assertNotIn("/policy/scripts/install_agent_policy_skill.py", quick_start)


if __name__ == "__main__":
    unittest.main()
