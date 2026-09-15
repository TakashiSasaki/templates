from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AudienceRuntimeJavaScriptFailNeutralTests(unittest.TestCase):
    def test_unmapped_route_does_not_inherit_stored_journey(self) -> None:
        js_code = (ROOT / "assets/javascripts/audience-context.js").read_text(encoding="utf-8")

        # Stored journey context is valid only when the current document declares
        # membership. An unmapped/unclassified route has no such membership and
        # must therefore remain neutral instead of fabricating Use/Maintain state.
        self.assertIn("if (meta.audiences.has(journey)) return journey;", js_code)
        self.assertIn("return meta.primary || null;", js_code)
        self.assertNotIn("return meta.primary || journey || null;", js_code)


if __name__ == "__main__":
    unittest.main()
