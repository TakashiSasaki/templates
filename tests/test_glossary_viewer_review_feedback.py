from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_glossary import generate_publication
from scripts.generate_glossary_viewer import GlossaryViewerError, load_model, render, source_url
from scripts.glossary import GlossaryError

REV = "a" * 40

def repository_term() -> dict[str, object]:
    return {"id":"templates-example","term":"Example","aliases":[],"origin":"repository","definition":"Canonical definition.","provider":"site","source_path":"docs/glossary.yml","source_revision":REV}

def external_term() -> dict[str, object]:
    return {"id":"external-git-branch","term":"Branch","aliases":[],"origin":"external","summary":"A Git branch.","authority":{"kind":"upstream","sources":[{"title":"Git glossary","url":"https://git-scm.com/docs/gitglossary"}]},"provider":"site","source_path":"docs/glossary.yml","source_revision":REV}

def model(*terms: dict[str, object], repository: str="TakashiSasaki/templates") -> dict[str, object]:
    return {"schema_version":1,"repository":repository,"terms":list(terms)}

class GlossaryViewerReviewFeedbackTests(unittest.TestCase):
    def load(self,value:dict[str,object])->dict[str,object]:
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"index.json"; path.write_text(json.dumps(value,ensure_ascii=False),encoding="utf-8"); return load_model(path)
    def test_empty_integrated_glossary_is_valid(self)->None:
        page=render(self.load(model())); self.assertIn("0</strong>total concepts",page)
    def test_japanese_regional_tag_is_canonicalized_and_counted(self)->None:
        term=repository_term(); term["localized_labels"]={"ja-jp":{"term":"例","aliases":[]}}; loaded=self.load(model(term)); self.assertIn("ja-JP",loaded["terms"][0]["localized_labels"])  # type: ignore[index]
        self.assertIn("1</strong>with Japanese labels",render(loaded))
    def test_localized_english_label_is_rejected(self)->None:
        term=repository_term(); term["localized_labels"]={"en-US":{"term":"Example US","aliases":[]}}
        with self.assertRaisesRegex(GlossaryViewerError,"canonical English"): self.load(model(term))
    def test_self_related_term_is_rejected(self)->None:
        term=repository_term(); term["related_terms"]=["templates-example"]
        with self.assertRaisesRegex(GlossaryViewerError,"term itself"): self.load(model(term))
    def test_repository_term_with_authority_is_rejected(self)->None:
        term=repository_term(); term["authority"]=external_term()["authority"]
        with self.assertRaisesRegex(GlossaryViewerError,"authority is not allowed"): self.load(model(term))
    def test_external_term_with_definition_is_rejected(self)->None:
        term=external_term(); term["definition"]="Forbidden."
        with self.assertRaisesRegex(GlossaryViewerError,"definition is not allowed"): self.load(model(term))
    def test_origin_specific_id_namespace_is_enforced(self)->None:
        term=repository_term(); term["id"]="external-git-example"
        with self.assertRaisesRegex(GlossaryViewerError,"must start with templates-"): self.load(model(term))
    def test_repository_dot_segments_are_rejected(self)->None:
        with self.assertRaisesRegex(GlossaryViewerError,"safe owner/name"): self.load(model(repository_term(),repository="../victim"))
        with self.assertRaisesRegex(GlossaryViewerError,"safe owner/name"): source_url("../victim",repository_term())
    def test_repository_summary_and_usage_are_both_rendered_and_escaped(self)->None:
        term=repository_term(); term["summary"]="Short <summary>."; term["repository_usage"]="Used by <site>."; page=render(self.load(model(term)))
        self.assertIn("Canonical definition.",page); self.assertIn("Short &lt;summary&gt;.",page); self.assertIn("Used by &lt;site&gt;.",page)
    def test_non_json_publication_output_is_rejected_before_writing(self)->None:
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"glossary.html"
            with self.assertRaisesRegex(GlossaryError,"must use a .json suffix"): generate_publication([],[],"TakashiSasaki/templates",output)
            self.assertFalse(output.exists())

if __name__ == "__main__": unittest.main()
