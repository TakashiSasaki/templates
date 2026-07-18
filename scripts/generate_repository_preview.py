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

from pygments import lex
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
from pygments.lexers.special import TextLexer
from pygments.token import STANDARD_TYPES
from pygments.util import ClassNotFound

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


def token_css_class(token_type: object) -> str:
    current = token_type
    while current not in STANDARD_TYPES and getattr(current, "parent", None) is not None:
        current = current.parent
    return STANDARD_TYPES.get(current, "")


def lexer_for_path(path: str, content: str) -> object:
    compound_lexers = {
        ".html.j2": "html+jinja",
        ".htm.j2": "html+jinja",
        ".yaml.j2": "yaml+jinja",
        ".yml.j2": "yaml+jinja",
    }
    for suffix, alias in compound_lexers.items():
        if path.endswith(suffix):
            return get_lexer_by_name(alias, stripnl=False, ensurenl=False)
    if path.endswith(".j2"):
        return get_lexer_by_name("jinja", stripnl=False, ensurenl=False)

    try:
        return get_lexer_for_filename(
            path,
            content,
            stripnl=False,
            ensurenl=False,
        )
    except ClassNotFound:
        return TextLexer(stripnl=False, ensurenl=False)


def highlight_content(path: str, content: str) -> dict[str, object]:
    lexer = lexer_for_path(path, content)

    lines: list[list[list[str]]] = [[]]
    for token_type, value in lex(content, lexer):
        css_class = token_css_class(token_type)
        parts = value.split("\n")
        for index, part in enumerate(parts):
            if part:
                lines[-1].append([css_class, part])
            if index < len(parts) - 1:
                lines.append([])

    return {
        "lexer": lexer.name,
        "lines": lines,
        "version": 1,
    }


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
        highlight_url = None
        lexer_name = None

        if kind in {"text", "image"}:
            asset_name = f"{blob_sha}{asset_suffix(kind, path)}"
            asset_path = branch_root / asset_name
            if not asset_path.exists():
                asset_path.write_bytes(content)
            asset_url = f"/generated/repository-preview/{quote(branch, safe='')}/{asset_name}"

        if kind == "text":
            highlighted = highlight_content(path, content.decode("utf-8"))
            lexer_name = str(highlighted["lexer"])
            path_digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:12]
            highlight_name = f"{blob_sha}-{path_digest}.tokens.json"
            highlight_path = branch_root / highlight_name
            highlight_path.write_text(
                json.dumps(highlighted, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            highlight_url = (
                f"/generated/repository-preview/{quote(branch, safe='')}/{highlight_name}"
            )

        files[path] = {
            "asset_url": asset_url,
            "blob": blob_sha,
            "github_url": github_url(commit, path),
            "highlight_url": highlight_url,
            "kind": kind,
            "lexer": lexer_name,
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
        "version": 2,
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
