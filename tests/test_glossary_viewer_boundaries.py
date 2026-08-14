from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_glossary_viewer import GlossaryViewerError, load_model

REVISION = "a" * 40

def model() -> dict[str, object]:
    return {"schema_version":1,"repository":"TakashiSasaki/templates","terms":[{"id":"external-git-branch","term":"Branch","aliases":[],"origin":"external","summary":"A named line of development in Git.","authority":{"kind":"upstream","sources":[{"title":"Git glossary","url":"https://git-scm.com/docs/gitglossary"}]},"provider":"site","source_path":"docs/glossary.yml","source_revision":REVISION}]}

def write_model(root: Path, value: dict[str, object]) -> Path:
    path=root/"index.json"; path.write_text(json.dumps(value),encoding="utf-8"); return path

class GlossaryViewerBoundaryTests(unittest.TestCase):
    def test_invalid_authority_kind_is_rejected(self) -> None:
        value=model(); value["terms"][0]["authority"]["kind"]="informal"  # type: ignore[index]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(GlossaryViewerError,"normative, upstream, or conventional"): load_model(write_model(Path(directory),value))
    def test_repository_identifier_must_be_owner_name(self) -> None:
        value=model(); value["repository"]="TakashiSasaki/templates/extra"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(GlossaryViewerError,"owner/name"): load_model(write_model(Path(directory),value))
    def test_symlinked_json_input_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); target=write_model(root,model()); link=root/"linked.json"; link.symlink_to(target)
            with self.assertRaisesRegex(GlossaryViewerError,"regular file"): load_model(link)
    def test_authority_url_with_whitespace_is_rejected(self) -> None:
        value=model(); value["terms"][0]["authority"]["sources"][0]["url"]="https://example.com/spec path"  # type: ignore[index]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(GlossaryViewerError,"valid HTTPS URL"): load_model(write_model(Path(directory),value))
    def test_unsafe_source_path_is_rejected(self) -> None:
        value=model(); value["terms"][0]["source_path"]="../docs/glossary.yml"  # type: ignore[index]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(GlossaryViewerError,"safe relative \\.yml path"): load_model(write_model(Path(directory),value))
    def test_pages_pipeline_validates_landing_link_to_glossary(self) -> None:
        root=Path(__file__).resolve().parents[1]; workflow=(root/".github/workflows/build-pages.yml").read_text(encoding="utf-8"); landing=(root/"docs/landing.md").read_text(encoding="utf-8")
        self.assertIn('href="/glossary/"',landing); self.assertIn("scripts/validate_site_links.py",workflow); self.assertIn("scripts/generate_glossary.py",workflow)

if __name__ == "__main__": unittest.main()
