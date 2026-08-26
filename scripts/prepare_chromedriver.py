#!/usr/bin/env python3
"""Prepare a ChromeDriver compatible with the installed Google Chrome build."""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+\.\d+)\b")
LATEST_RELEASE_BASE = "https://googlechromelabs.github.io/chrome-for-testing"
DOWNLOAD_BASE = "https://storage.googleapis.com/chrome-for-testing-public"
ARCHIVE_MEMBER = "chromedriver-linux64/chromedriver"
USER_AGENT = "TakashiSasaki-templates-composition-ci/1"


class ChromeDriverPreparationError(RuntimeError):
    pass


def parse_four_part_version(text: str) -> str:
    """Extract one four-part Chrome-family version from command output."""
    match = VERSION_RE.search(text)
    if match is None:
        raise ChromeDriverPreparationError(
            f"could not parse a four-part version from: {text.strip()!r}"
        )
    return match.group(1)


def version_build(version: str) -> str:
    """Return MAJOR.MINOR.BUILD from a validated four-part version."""
    if VERSION_RE.fullmatch(version) is None:
        raise ChromeDriverPreparationError(f"invalid four-part version: {version!r}")
    return version.rsplit(".", 1)[0]


def resolve_driver_version(chrome_version: str, release_text: str) -> str:
    """Validate the CfT latest-release response for Chrome's build triplet."""
    driver_version = release_text.strip()
    if VERSION_RE.fullmatch(driver_version) is None:
        raise ChromeDriverPreparationError(
            f"CfT returned an invalid ChromeDriver version: {driver_version!r}"
        )
    chrome_build = version_build(chrome_version)
    if version_build(driver_version) != chrome_build:
        raise ChromeDriverPreparationError(
            "CfT ChromeDriver build does not match installed Chrome: "
            f"chrome={chrome_version}, driver={driver_version}"
        )
    return driver_version


def latest_release_url(chrome_version: str) -> str:
    return f"{LATEST_RELEASE_BASE}/LATEST_RELEASE_{version_build(chrome_version)}"


def driver_archive_url(driver_version: str) -> str:
    if VERSION_RE.fullmatch(driver_version) is None:
        raise ChromeDriverPreparationError(
            f"invalid ChromeDriver version: {driver_version!r}"
        )
    return (
        f"{DOWNLOAD_BASE}/{driver_version}/linux64/"
        "chromedriver-linux64.zip"
    )


def _request(url: str) -> Request:
    return Request(url, headers={"User-Agent": USER_AGENT})


def download_text(url: str) -> str:
    try:
        with urlopen(_request(url), timeout=20) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ChromeDriverPreparationError(f"failed to download {url}: {exc}") from exc


def download_bytes(url: str) -> bytes:
    try:
        with urlopen(_request(url), timeout=30) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ChromeDriverPreparationError(f"failed to download {url}: {exc}") from exc


def write_driver_from_zip(archive: bytes, destination: Path) -> None:
    """Write only the expected driver member; never extract arbitrary archive paths."""
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            info = bundle.getinfo(ARCHIVE_MEMBER)
            if info.is_dir() or info.file_size <= 0:
                raise ChromeDriverPreparationError(
                    f"ChromeDriver archive member is not a non-empty file: {ARCHIVE_MEMBER}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, tempfile.NamedTemporaryFile(
                dir=destination.parent,
                prefix=".chromedriver-",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                shutil.copyfileobj(source, temporary)
    except (KeyError, zipfile.BadZipFile, OSError) as exc:
        raise ChromeDriverPreparationError(
            f"invalid ChromeDriver archive: {exc}"
        ) from exc

    try:
        temporary_path.chmod(0o755)
        temporary_path.replace(destination)
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise ChromeDriverPreparationError(
            f"failed to install ChromeDriver at {destination}: {exc}"
        ) from exc


def command_version(command: str | Path) -> str:
    result = subprocess.run(
        [str(command), "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ChromeDriverPreparationError(
            f"{command} --version failed with exit {result.returncode}"
            + (f": {detail}" if detail else "")
        )
    return parse_four_part_version(result.stdout or result.stderr)


def prepare_driver(chrome_command: str, output_dir: Path) -> tuple[Path, str, str]:
    chrome_version = command_version(chrome_command)
    release_url = latest_release_url(chrome_version)
    driver_version = resolve_driver_version(
        chrome_version,
        download_text(release_url),
    )
    archive_url = driver_archive_url(driver_version)
    destination = output_dir / "chromedriver"
    write_driver_from_zip(download_bytes(archive_url), destination)
    installed_version = command_version(destination)
    if installed_version != driver_version:
        raise ChromeDriverPreparationError(
            "downloaded ChromeDriver version does not match resolved version: "
            f"resolved={driver_version}, installed={installed_version}"
        )
    return destination.resolve(), chrome_version, driver_version


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chrome-command", default="google-chrome")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        driver, chrome_version, driver_version = prepare_driver(
            args.chrome_command,
            args.output_dir,
        )
    except ChromeDriverPreparationError as exc:
        print(f"ChromeDriver preparation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Prepared ChromeDriver {driver_version} for Chrome {chrome_version}",
        file=sys.stderr,
    )
    print(driver)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
