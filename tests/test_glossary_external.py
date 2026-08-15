from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.glossary import integrate_glossaries, load_glossary


EXTERNAL_MCP = """schema_version: 1
terms:
  - id: external-mcp-model-context-protocol
    term: Model Context Protocol
    aliases:
      - MCP
    origin: external
    summary: An open protocol for connecting LLM applications to external capabilities.
    authority:
      kind: normative
      sources:
        - title: Model Context Protocol Specification
          url: https://modelcontextprotocol.io/specification/2026-07-28
          version: "2026-07-28"
"""

SKILL_WITH_EXTERNAL_MCP = """schema_version: 1
terms:
  - id: templates-skill-mcp-extension
    term: Skill MCP extension
    origin: repository
    definition: An MCP extension identifier selected for an MCP-enabled Skill.
    related_terms:
      - external-mcp-model-context-protocol

  - id: external-mcp-model-context-protocol
    term: Model Context Protocol
    aliases:
      - MCP
    origin: external
    summary: An open protocol for connecting LLM applications to external capabilities.
    authority:
      kind: normative
      sources:
        - title: Model Context Protocol Specification
          url: https://modelcontextprotocol.io/specification/2026-07-28
          version: "2026-07-28"
"""


class ExternalGlossaryUnitTests(unittest.TestCase):
    def test_external_aliases_are_preserved_by_loader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "glossary.yml"
            path.write_text(EXTERNAL_MCP, encoding="utf-8")
            terms = load_glossary(path)

        self.assertEqual(terms[0]["aliases"], ["MCP"])

    def test_provider_local_external_relation_resolves_in_integration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = Path(directory) / "skill"
            docs = provider / "docs"
            docs.mkdir(parents=True)
            (docs / "glossary.yml").write_text(
                SKILL_WITH_EXTERNAL_MCP,
                encoding="utf-8",
            )
            (docs / "publication-catalog.json").write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "documents": [
                            {
                                "id": "overview",
                                "source": "README.md",
                                "optional": False,
                                "home": True,
                            }
                        ],
                        "glossary": {"source": "docs/glossary.yml"},
                    }
                ),
                encoding="utf-8",
            )

            value = integrate_glossaries(
                {"skill": provider},
                {"skill": "1" * 40},
                "TakashiSasaki/templates",
            )

        by_id = {term["id"]: term for term in value["terms"]}
        self.assertEqual(
            by_id["templates-skill-mcp-extension"]["related_terms"],
            ["external-mcp-model-context-protocol"],
        )
        self.assertEqual(
            by_id["templates-skill-mcp-extension"]["provider"],
            "skill",
        )
        self.assertEqual(
            by_id["external-mcp-model-context-protocol"]["provider"],
            "skill",
        )
        self.assertEqual(
            by_id["external-mcp-model-context-protocol"]["origin"],
            "external",
        )


if __name__ == "__main__":
    unittest.main()
