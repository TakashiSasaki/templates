"""Project Site/deployment runtime identity from the adopted Integration release."""
from pathlib import Path
from scripts import generate_freshness_metadata

def project_freshness_metadata(
    output: Path,
    site_commit: str,
    publication_commits: dict[str, str],
) -> tuple[Path, int] | None:
    """Project build provenance into public freshness metadata for a built Site tree."""
    site_root = output.parent
    if not (site_root / "index.html").is_file():
        return None
    deployment_timestamp = generate_freshness_metadata.deployment_timestamp_from_index(
        site_root
    )
    return generate_freshness_metadata.generate_freshness_metadata(
        site_root,
        site_commit,
        deployment_timestamp,
        publication_commits,
    )

