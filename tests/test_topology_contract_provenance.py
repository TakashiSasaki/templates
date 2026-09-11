import hashlib
import json
import subprocess
from pathlib import Path


def test_topology_snapshot_is_exact_composition_source() -> None:
    root = Path(__file__).resolve().parents[1]
    bundle = root / "src/agent_policy/_topology_contract"
    source = json.loads((bundle / "source.json").read_text())
    assert source["authority"] == "composition"
    assert source["repository"] == "TakashiSasaki/templates"
    for entry in source["files"]:
        data = (bundle / entry["destination"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        original = subprocess.check_output(
            ["git", "show", f"{source['revision']}:{entry['source']}"], cwd=root,
        )
        assert data == original
