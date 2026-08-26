from __future__ import annotations

import json
import subprocess
from pathlib import Path

OLD = "d27b677c5eb2366a35326e955a9d1766bfd41cff"
NEW = "7e1352a527cdfa6a20ac5df1a81b404b4a6699b3"

for path in (
    "docs/guides/webapp-product-walkthrough.md",
    "translations/ja/docs/guides/webapp-product-walkthrough.md",
    "tests/test_human_first_webapp_onboarding.py",
):
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f"{path}: expected one old revision, found {count}")
    file.write_text(text.replace(OLD, NEW), encoding="utf-8")

manifest_path = Path("translations/manifest.json")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
canonical = "docs/guides/webapp-product-walkthrough.md"
sha = subprocess.check_output(["git", "hash-object", canonical], text=True).strip()
for entry in manifest["translations"]:
    if entry["canonical"] == canonical:
        entry["canonical_blob_sha"] = sha
        break
else:
    raise SystemExit(f"missing translation manifest entry: {canonical}")
manifest_path.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
