from pathlib import Path
from runpy import run_path

MODULE = run_path(
    str(Path(__file__).parents[1] / "scripts" / "generate_repository_preview.py")
)
MAX_PREVIEW_BYTES = MODULE["MAX_PREVIEW_BYTES"]
classify_content = MODULE["classify_content"]


def test_classify_utf8_text() -> None:
    kind, _ = classify_content("example.py", b"print('ok')\n")
    assert kind == "text"


def test_classify_png_image() -> None:
    kind, mime_type = classify_content("icon.png", b"\x89PNG\r\n\x1a\n")
    assert kind == "image"
    assert mime_type == "image/png"


def test_classify_binary_content() -> None:
    kind, _ = classify_content("data.bin", b"abc\x00def")
    assert kind == "binary"


def test_classify_large_content() -> None:
    kind, _ = classify_content("large.txt", b"x" * (MAX_PREVIEW_BYTES + 1))
    assert kind == "too-large"
