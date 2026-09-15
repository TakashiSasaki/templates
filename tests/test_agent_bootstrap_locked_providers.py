"""The actual provider descriptor case runs with the materialized producer inputs."""
import unittest
from pathlib import Path
from scripts import generate_agent_bootstrap as bootstrap
from tests.publication_context import provider_root
ROOT = Path(__file__).resolve().parents[1]

class LockedProviderBootstrapTests(unittest.TestCase):
    def test_exact_checked_out_provider_descriptors_match_projection_when_available(self) -> None:
        composition_root = provider_root("composition", ROOT)
        policy_root = provider_root("policy", ROOT)
        composition_release = composition_root / bootstrap.COMPOSITION_RELEASE_PATH
        policy_release = policy_root / bootstrap.POLICY_RELEASE_PATH
        if not composition_release.is_file() or not policy_release.is_file():
            self.skipTest("exact provider publication checkouts are not available")
        bootstrap.verify_site_projections(ROOT, composition_root, policy_root)
