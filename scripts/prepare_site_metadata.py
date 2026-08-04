#!/usr/bin/env python3
"""Prepare deployment-specific metadata in an assembled Zensical config."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit


DEPLOYMENT_TIMESTAMP_PATTERN = re.compile(
    r"\A\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} JST\Z"
)
PROJECT_HEADER_PATTERN = re.compile(r"(?m)^\[project\][ \t]*$")
COPYRIGHT_PATTERN = re.compile(r"(?m)^copyright[ \t]*=")


class SiteMetadataError(RuntimeError):
    """Raised when generated site metadata cannot be prepared safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", required=True, type=Path)
    parser.add_argument("--deployment-timestamp", default="")
    parser.add_argument("--canonical-url", required=True)
    return parser.parse_args()


def validate_canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.path.endswith("/")
        or parsed.query
        or parsed.fragment
    ):
        raise SiteMetadataError(
            "canonical URL must be an HTTPS directory URL without query or fragment"
        )
    return value


def deployment_notice(timestamp: str) -> str:
    if not timestamp:
        return "Preview build (not deployed)"
    if DEPLOYMENT_TIMESTAMP_PATTERN.fullmatch(timestamp) is None:
        raise SiteMetadataError(
            "deployment timestamp must use YYYY-MM-DD HH:MM:SS JST"
        )
    return f"Deployment time: {timestamp}"


def prepare_config(
    config_file: Path,
    deployment_timestamp: str,
    canonical_url: str,
) -> str:
    canonical_url = validate_canonical_url(canonical_url)
    try:
        raw = config_file.read_bytes()
    except OSError as exc:
        raise SiteMetadataError(f"unable to read config {config_file}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SiteMetadataError(f"config must be valid UTF-8: {config_file}") from exc

    try:
        config = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise SiteMetadataError(f"unable to parse config {config_file}: {exc}") from exc
    project = config.get("project")
    if not isinstance(project, dict):
        raise SiteMetadataError("config must contain a [project] table")
    if project.get("site_url") != canonical_url:
        raise SiteMetadataError(
            f"project.site_url must be the public URL {canonical_url!r}"
        )
    if "copyright" in project:
        raise SiteMetadataError(
            "assembled config must not define project.copyright before metadata preparation"
        )

    headers = list(PROJECT_HEADER_PATTERN.finditer(text))
    if len(headers) != 1:
        raise SiteMetadataError("config must contain exactly one [project] header")

    project_start = headers[0].end()
    next_table = re.search(r"(?m)^\[", text[project_start:])
    project_end = (
        project_start + next_table.start() if next_table is not None else len(text)
    )
    if COPYRIGHT_PATTERN.search(text[project_start:project_end]) is not None:
        raise SiteMetadataError("project.copyright is already defined")

    notice = deployment_notice(deployment_timestamp)
    insertion = "\ncopyright = " + json.dumps(notice, ensure_ascii=False)
    updated = text[:project_start] + insertion + text[project_start:]

    try:
        parsed_updated = tomllib.loads(updated)
    except tomllib.TOMLDecodeError as exc:
        raise SiteMetadataError(
            f"prepared config is not valid TOML: {config_file}: {exc}"
        ) from exc
    updated_project = parsed_updated.get("project")
    if not isinstance(updated_project, dict):
        raise SiteMetadataError("prepared config lost the [project] table")
    if updated_project.get("copyright") != notice:
        raise SiteMetadataError("prepared config did not preserve the deployment notice")

    config_file.write_text(updated, encoding="utf-8")
    return notice


def main() -> int:
    args = parse_args()
    try:
        notice = prepare_config(
            args.config_file,
            args.deployment_timestamp,
            args.canonical_url,
        )
    except (OSError, SiteMetadataError) as exc:
        print(f"prepare_site_metadata.py: {exc}", file=sys.stderr)
        return 1
    print(notice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
