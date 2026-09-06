from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications_v3 import AssemblyError, materialize_provider_publication_assets


class ProviderPublicationMaterializationTests(unittest.TestCase):
    def test_no_composition_provider_is_a_noop(self) -> None:
        materialize_provider_publication_assets({})

    def test_manifest_without_provider_generator_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "generated" / "composition-playground-publication.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(AssemblyError):
                materialize_provider_publication_assets({"composition": root})

    def test_site_invokes_provider_owned_generator_without_resolving(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "generated"
            scripts = root / "scripts"
            generated.mkdir(parents=True)
            scripts.mkdir(parents=True)
            (generated / "composition-playground-publication.json").write_text("{}\n", encoding="utf-8")
            generator = scripts / "generate_composition_playground_publication.py"
            generator.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "target = Path(sys.argv[sys.argv.index('--output-dir') + 1])\n"
                "(target / 'provider-generator-ran').write_text('yes\\n')\n",
                encoding="utf-8",
            )
            materialize_provider_publication_assets({"composition": root})
            self.assertEqual("yes\n", (generated / "provider-generator-ran").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
