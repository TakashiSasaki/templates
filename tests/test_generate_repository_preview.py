from pathlib import Path
from runpy import run_path

MODULE = run_path(
    str(Path(__file__).parents[1] / "scripts" / "generate_repository_preview.py")
)
MAX_PREVIEW_BYTES = MODULE["MAX_PREVIEW_BYTES"]
classify_content = MODULE["classify_content"]
highlight_content = MODULE["highlight_content"]


def reconstructed_content(payload: dict[str, object]) -> str:
    lines = payload["lines"]
    assert isinstance(lines, list)
    return "\n".join(
        "".join(token[1] for token in line)
        for line in lines
    )


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


def test_highlight_python_preserves_content() -> None:
    content = "def greet(name):\n    return f'Hello, {name}'\n"
    highlighted = highlight_content("example.py", content)

    assert highlighted["lexer"] == "Python"
    assert reconstructed_content(highlighted) == content
    assert any(
        token_class
        for line in highlighted["lines"]
        for token_class, _ in line
    )


def test_highlight_unknown_extension_falls_back_to_plain_text() -> None:
    content = "unclassified content\n"
    highlighted = highlight_content("example.unknown-extension", content)

    assert highlighted["lexer"] == "Text only"
    assert reconstructed_content(highlighted) == content
    assert all(
        not token_class
        for line in highlighted["lines"]
        for token_class, _ in line
    )


def test_highlight_jinja_yaml_uses_compound_lexer() -> None:
    content = "uses: {{ revision }}\n"
    highlighted = highlight_content("workflow.yml.j2", content)

    assert highlighted["lexer"] == "YAML+Jinja"
    assert reconstructed_content(highlighted) == content
