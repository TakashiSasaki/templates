from pathlib import Path
import json
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AudienceRuntimeJavaScriptFailNeutralTests(unittest.TestCase):
    def run_javascript(self, assertion: str) -> None:
        runtime_path = json.dumps(str(ROOT / "assets/javascripts/audience-context.js"))
        harness = f"""
const fs = require("node:fs");
const vm = require("node:vm");
global.location = {{ pathname: "/unmapped/", href: "https://example.test/unmapped/" }};
global.history = {{
  state: null,
  replaceState(state) {{ this.state = state; }},
  pushState(state) {{ this.state = state; }},
}};
global.sessionStorage = {{ getItem() {{ return "maintain"; }}, setItem() {{}} }};
global.document = {{
  readyState: "loading",
  addEventListener() {{}},
  querySelectorAll() {{ return []; }},
  documentElement: {{ dataset: {{}} }},
}};
global.window = {{
  addEventListener() {{}},
  dispatchEvent() {{}},
  document$: null,
}};
global.CustomEvent = class {{}};
global.fetch = async () => {{ throw new Error("not used"); }};
vm.runInThisContext(fs.readFileSync({runtime_path}, "utf8"), {{ filename: {runtime_path} }});
{assertion}
"""
        completed = subprocess.run(
            ["node", "-e", harness],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_unmapped_route_does_not_inherit_stored_journey(self) -> None:
        self.run_javascript("""
const resolved = window.TemplatesAudienceContext.resolveAudienceWithMetadata({
  isLanding: false,
  audiences: new Set(),
  primary: null,
});
if (resolved !== null) throw new Error(`unmapped route resolved to ${resolved}`);
""")

    def test_same_document_push_state_preserves_recorded_audience(self) -> None:
        self.run_javascript("""
history.state = {
  templatesAudienceContext: { path: "/unmapped/", audience: "maintain" },
};
history.pushState(null, "", "#selected-file");
if (history.state?.templatesAudienceContext?.audience !== "maintain") {
  throw new Error("same-document pushState lost the recorded audience");
}
history.pushState(null, "", "/another-document/");
if (history.state?.templatesAudienceContext) {
  throw new Error("new-document pushState inherited the recorded audience");
}
""")


if __name__ == "__main__":
    unittest.main()
