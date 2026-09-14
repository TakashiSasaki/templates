import hashlib
import json
import subprocess
from pathlib import Path

COMPOSITION_C2_REVISION = "8c6c1884fa97f3ef1ec6c1aa7deba4ad38c9f4ff"


def test_local_checkout_snapshot_is_exact_composition_source() -> None:
    root = Path(__file__).resolve().parents[1]
    bundle = root / "src/agent_policy/_local_checkout_contract"
    source = json.loads((bundle / "source.json").read_text())
    assert source["authority"] == "composition"
    assert source["repository"] == "TakashiSasaki/templates"
    assert source["revision"] == COMPOSITION_C2_REVISION
    for entry in source["files"]:
        data = (bundle / entry["destination"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        original = subprocess.check_output(
            ["git", "show", f"{source['revision']}:{entry['source']}"], cwd=root,
        )
        assert data == original
