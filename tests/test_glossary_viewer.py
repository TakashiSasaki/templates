from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_glossary import generate_publication
from scripts.generate_glossary_viewer import GlossaryViewerError, generate, load_model, render

REV_SITE = "1" * 40
REV_POLICY = "2" * 40
REV_COMPOSITION = "3" * 40

def sample_model() -> dict[str, object]:
    return {"schema_version": 1, "repository": "TakashiSasaki/templates", "terms": [
        {"id":"templates-policy-context","term":"Policy context","aliases":[],"localized_labels":{"ja":{"term":"ポリシーコンテキスト","aliases":["方針コンテキスト"]}},"origin":"repository","definition":"A semantic authority boundary.","related_terms":["templates-policy-renderer"],"provider":"policy","source_path":"docs/glossary.yml","source_revision":REV_POLICY},
        {"id":"templates-policy-renderer","term":"Policy renderer","aliases":["Renderer"],"origin":"repository","definition":"A presentation adapter.","provider":"policy","source_path":"docs/glossary.yml","source_revision":REV_POLICY},
        {"id":"templates-composition-component","term":"Composition component","aliases":[],"localized_labels":{"ja":{"term":"コンポジションコンポーネント","aliases":[]}},"origin":"repository","definition":"A reusable Composition source authority.","provider":"composition","source_path":"docs/glossary.yml","source_revision":REV_COMPOSITION},
        {"id":"external-git-branch","term":"Branch","aliases":[],"localized_labels":{"ja":{"term":"ブランチ","aliases":[]}},"origin":"external","summary":"A named line of development in Git.","authority":{"kind":"upstream","sources":[{"title":"Git glossary","url":"https://git-scm.com/docs/gitglossary","locator":"branch"}]},"provider":"site","source_path":"docs/glossary.yml","source_revision":REV_SITE}
    ]}

class GlossaryViewerTests(unittest.TestCase):
    def write_model(self, root: Path, model: dict[str, object] | None = None) -> Path:
        path = root / "index.json"
        path.write_text(json.dumps(sample_model() if model is None else model, ensure_ascii=False), encoding="utf-8")
        return path
    def test_renders_repository_and_external_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = load_model(self.write_model(Path(directory)))
        page = render(model)
        for text in ("Templates-defined terms","Externally defined terms","Policy context","ポリシーコンテキスト","方針コンテキスト","Composition component","Composition","External authority:","Git glossary"):
            self.assertIn(text, page)
        self.assertIn("4</strong>total concepts", page)
    def test_current_provider_order_places_composition_before_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            page = render(load_model(self.write_model(Path(directory))))
        self.assertLess(page.index('id="provider-composition"'), page.index('id="provider-policy"'))
        self.assertNotIn('id="provider-skill"', page)
        self.assertNotIn('id="provider-webapp"', page)
    def test_inline_popup_uses_current_provider_labels(self) -> None:
        script=(Path(__file__).resolve().parents[1]/"assets/javascripts/glossary-inline.js").read_text(encoding="utf-8")
        self.assertIn('composition: "Composition"', script)
        self.assertNotIn('skill: "Skill"', script)
        self.assertNotIn('webapp: "Webapp"', script)
    def test_related_terms_use_stable_id_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            page = render(load_model(self.write_model(Path(directory))))
        self.assertIn('id="templates-policy-context"', page)
        self.assertIn('href="#templates-policy-renderer"', page)
    def test_source_link_uses_full_locked_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            page = render(load_model(self.write_model(Path(directory))))
        self.assertIn("https://github.com/TakashiSasaki/templates/blob/" + REV_POLICY + "/docs/glossary.yml", page)
    def test_user_visible_text_is_html_escaped(self) -> None:
        value = sample_model(); value["terms"][0]["term"] = "Policy <script>alert(1)</script> context"  # type: ignore[index]
        with tempfile.TemporaryDirectory() as directory:
            page = render(load_model(self.write_model(Path(directory), value)))
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("Policy &lt;script&gt;alert(1)&lt;/script&gt; context", page)
    def test_invalid_authority_scheme_is_rejected(self) -> None:
        value = sample_model(); value["terms"][-1]["authority"]["sources"][0]["url"] = "javascript:alert(1)"  # type: ignore[index]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(GlossaryViewerError, "valid HTTPS URL"):
                load_model(self.write_model(Path(directory), value))
    def test_unknown_related_term_is_rejected(self) -> None:
        value = sample_model(); value["terms"][0]["related_terms"] = ["templates-missing"]  # type: ignore[index]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(GlossaryViewerError, "unknown related term"):
                load_model(self.write_model(Path(directory), value))
    def test_generate_writes_page_next_to_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); input_path=self.write_model(root); output_path=root/"index.html"; generate(input_path,output_path); page=output_path.read_text(encoding="utf-8")
        self.assertIn("<h1>Glossary</h1>", page)
        self.assertIn('href="/glossary/index.json"', page)
    def test_publication_cli_layer_writes_sibling_html(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); publication=root/"site"; (publication/"docs").mkdir(parents=True)
            (publication/"docs/publication-catalog.json").write_text(json.dumps({"schema_version":3,"documents":[{"id":"home","source":"docs/home.md","optional":False,"home":True}],"glossary":{"source":"docs/glossary.yml"}}),encoding="utf-8")
            (publication/"docs/home.md").write_text("# Home\n",encoding="utf-8")
            (publication/"docs/glossary.yml").write_text("schema_version: 1\nterms:\n  - id: templates-example\n    term: Example\n    origin: repository\n    definition: Example definition.\n",encoding="utf-8")
            output=root/"glossary/index.json"; viewer=generate_publication([f"site={publication}"],["site="+"a"*40],"TakashiSasaki/templates",output)
            self.assertTrue(output.is_file()); self.assertTrue(viewer.is_file())
    def test_landing_page_links_to_generated_glossary(self) -> None:
        landing=(Path(__file__).resolve().parents[1]/"docs/landing.md").read_text(encoding="utf-8")
        self.assertIn('href="/glossary/"',landing)
    def test_pages_workflow_still_calls_integrated_glossary_cli(self) -> None:
        workflow=(Path(__file__).resolve().parents[1]/".github/workflows/build-pages.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/generate_glossary.py",workflow)
        self.assertIn("--output build/site/glossary/index.json",workflow)

if __name__ == "__main__": unittest.main()
