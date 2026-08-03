from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs/build-info.json"
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_PATTERN = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"
)
JST = ZoneInfo("Asia/Tokyo")


def build_metadata(
    *,
    commit: str,
    repository: str,
    run_id: int,
    run_number: int,
    built_at: datetime,
) -> dict[str, Any]:
    if COMMIT_PATTERN.fullmatch(commit) is None:
        raise ValueError("commit must be a 40-character lowercase hexadecimal SHA")
    if REPOSITORY_PATTERN.fullmatch(repository) is None:
        raise ValueError("repository must use owner/repository syntax")
    if run_id < 0 or run_number < 0:
        raise ValueError("run identifiers must be non-negative integers")
    if built_at.tzinfo is None or built_at.utcoffset() is None:
        raise ValueError("built_at must be timezone-aware")

    built_at_utc = built_at.astimezone(UTC)
    return {
        "built_at_utc": built_at_utc.isoformat().replace("+00:00", "Z"),
        "built_at_jst": built_at_utc.astimezone(JST).isoformat(),
        "commit": commit,
        "repository": repository,
        "run_id": run_id,
        "run_number": run_number,
    }


def write_build_info(output: Path, metadata: Mapping[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(dict(metadata), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate documentation build metadata."
    )
    parser.add_argument("--commit", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", type=int, default=0)
    parser.add_argument("--run-number", type=int, default=0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        metadata = build_metadata(
            commit=args.commit,
            repository=args.repository,
            run_id=args.run_id,
            run_number=args.run_number,
            built_at=datetime.now(UTC),
        )
        write_build_info(args.output, metadata)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Documentation build metadata generation failed: {exc}") from exc

    print(f"Wrote documentation build metadata to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
