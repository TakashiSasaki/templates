"""Public destination to static URL projection."""
from pathlib import Path

def public_path(destination: str) -> str:
    path = Path(destination)
    if path.name == "index.md":
        parent = path.parent.as_posix()
        return "/" if parent == "." else f"/{parent}/"
    return "/" + path.with_suffix("").as_posix() + "/"

