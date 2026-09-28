#!/usr/bin/env python3
"""Observe a pinned OKF reference index generator; not an OKF conformance test.

Run only against a trusted upstream checkout. Source blobs must match the
selected observation record before their Python code is loaded. No network or
model call is made. All generated bundles are disposable temporary fixtures.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types


def blob_oid(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def observe(upstream_root: Path, pins: dict[str, str]) -> list[dict[str, object]]:
    paths = {
        "document": "src/reference_agent/bundle/document.py",
        "index": "src/reference_agent/bundle/index.py",
    }
    code = {}
    for name, relative in paths.items():
        data = (upstream_root / relative).read_bytes()
        if blob_oid(data) != pins[relative]:
            raise ValueError(f"source blob does not match observation: {relative}")
        code[name] = data.decode("utf-8")
    prefix = "reference_agent"
    saved = {k: v for k, v in sys.modules.items() if k == prefix or k.startswith(prefix + ".")}
    for key in saved:
        del sys.modules[key]
    try:
        for name in (prefix, prefix + ".bundle"):
            module = types.ModuleType(name)
            module.__path__ = []
            sys.modules[name] = module
        synth = types.ModuleType(prefix + ".bundle.synthesizer")
        def no_model(*args, **kwargs):
            raise AssertionError("default synthesizer must not be invoked by this probe")
        synth.synthesize_description = no_model
        sys.modules[synth.__name__] = synth
        for name in ("document", "index"):
            fullname = prefix + ".bundle." + name
            module = types.ModuleType(fullname)
            module.__file__ = str(upstream_root / paths[name])
            sys.modules[fullname] = module
            exec(compile(code[name], module.__file__, "exec"), module.__dict__)
        generator = sys.modules[prefix + ".bundle.index"].regenerate_indexes
        calls = []
        def stub(rel, children, *, model):
            calls.append(rel)
            return "Probe directory description"
        def concept(title="Alpha", kind="Reference"):
            return f"---\ntype: {kind}\ntitle: {title}\ndescription: Probe description.\n---\n\n# Content\n"
        observations = []
        def run(case, files):
            with tempfile.TemporaryDirectory(prefix="okf-observation-") as temp:
                root = Path(temp)
                for relative, value in files.items():
                    target = root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(value, encoding="utf-8")
                calls.clear()
                written = generator(root, model="offline-probe", synthesize=stub)
                return {
                    "id": case,
                    "written": sorted(p.relative_to(root).as_posix() for p in written),
                    "indexes": {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
                                for p in sorted(root.rglob("index.md"))},
                    "synthesis_calls": list(calls),
                }
        observations.append(run("P01", {"index.md": '---\nokf_version: "0.2"\n---\n\n# Curated\n\nRetain this explanation.\n', "alpha.md": concept()}))
        observations.append(run("P02", {"a/b/c/topic.md": concept()}))
        observations.append(run("P03", {"index.md": "# Tools\n\n* [Code](check.py) - Curated code description.\n", "alpha.md": concept(), "check.py": "pass\n", "query.sql": "SELECT 1;\n", "viz.html": "<!doctype html><title>View</title>\n"}))
        observations.append(run("P04", {"check.py": "pass\n"}))
        observations.append(run("P05", {"alpha.md": concept(), "empty/.keep": "", "code/check.py": "pass\n"}))
        observations.append(run("P06", {"log.md": "# Update log\n\n## 2026-09-28\n* Updated a definition.\n", "guide.md": "# No frontmatter\n"}))
        observations.append(run("P07", {"alpha.md": concept("Alpha", "Reference"), "beta.md": concept("Beta", "Metric")}))
        observations.append(run("P08", {"index.md": "# Tools\n\n* [Code](check.py) - Curated code description.\n", "check.py": "pass\n"}))
        return observations
    finally:
        for key in list(sys.modules):
            if key == prefix or key.startswith(prefix + "."):
                del sys.modules[key]
        sys.modules.update(saved)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trusted-upstream-root", type=Path, required=True)
    parser.add_argument("--observation", type=Path, required=True)
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.observation.read_text(encoding="utf-8"))
        pins = {s["path"]: s["blob"] for s in snapshot["sources"]}
        result = observe(args.trusted_upstream_root, pins)
        matches = result == snapshot["probes"]
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"kind": "reference-implementation-observations", "normative": False,
                      "networkUsed": False, "modelUsed": False,
                      "matchesRecordedProbes": matches, "probes": result}, indent=2))
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
