#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

REPOSITORY = "TakashiSasaki/agent-policy"
REMOTE_BOOTSTRAP_REF = "refs/remotes/origin/bootstrap-agent-policy"
BRANCH_REFS = {
    "main": "HEAD",
    "bootstrap-agent-policy": REMOTE_BOOTSTRAP_REF,
}
DEFAULT_OUTPUT = Path("docs/generated/repository-preview")
MAX_PREVIEW_BYTES = 512 * 1024
RASTER_MIME_TYPES = {"image/gif", "image/jpeg", "image/png", "image/webp"}


def run_git_bytes(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments],
        check=True,
        capture_output=True,
    ).stdout


def run_git_text(*arguments: str) -> str:
    return run_git_bytes(*arguments).decode("utf-8").strip()


def tracked_paths(ref: str) -> list[str]:
    output = run_git_bytes("ls-tree", "-r", "--name-only", "-z", ref)
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def classify_content(path: str, content: bytes) -> tuple[str, str]:
    mime_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if len(content) > MAX_PREVIEW_BYTES:
        return "too-large", mime_type
    if mime_type in RASTER_MIME_TYPES:
        return "image", mime_type
    if b"\0" in content:
        return "binary", mime_type
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return "binary", mime_type
    return "text", mime_type


def asset_suffix(kind: str, path: str) -> str:
    if kind == "text":
        return ".txt"
    suffix = Path(path).suffix.lower()
    return suffix if suffix in {".gif", ".jpeg", ".jpg", ".png", ".webp"} else ".bin"


def github_url(revision: str, path: str) -> str:
    encoded_revision = quote(revision, safe="")
    encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
    return f"https://github.com/{REPOSITORY}/blob/{encoded_revision}/{encoded_path}"


def generate_branch(branch: str, ref: str, output_root: Path) -> dict[str, object]:
    commit = run_git_text("rev-parse", ref)
    files: dict[str, object] = {}
    branch_root = output_root / branch
    branch_root.mkdir(parents=True, exist_ok=True)

    for path in tracked_paths(ref):
        blob_sha = run_git_text("rev-parse", f"{ref}:{path}")
        content = run_git_bytes("show", f"{ref}:{path}")
        kind, mime_type = classify_content(path, content)
        asset_url = None

        if kind in {"text", "image"}:
            asset_name = f"{blob_sha}{asset_suffix(kind, path)}"
            asset_path = branch_root / asset_name
            if not asset_path.exists():
                asset_path.write_bytes(content)
            asset_url = f"/generated/repository-preview/{quote(branch, safe='')}/{asset_name}"

        files[path] = {
            "asset_url": asset_url,
            "blob": blob_sha,
            "github_url": github_url(commit, path),
            "kind": kind,
            "mime_type": mime_type,
            "size": len(content),
        }

    return {"commit": commit, "files": files}


def generate(output_root: Path) -> Path:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    branches = {
        branch: generate_branch(branch, ref, output_root)
        for branch, ref in BRANCH_REFS.items()
    }
    manifest = {
        "branches": branches,
        "repository": REPOSITORY,
        "version": 1,
    }
    manifest_path = output_root / "index.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate static, same-origin repository file preview assets."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest_path = generate(args.output)
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    print(f"Generated {manifest_path} (sha256:{digest}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
