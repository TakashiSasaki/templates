import pytest

from scripts.generate_index_navigation import (
    IndexNavigationError,
    ParsedLink,
    parse_index,
    resolve_link,
)


def external_link(target: str) -> ParsedLink:
    return ParsedLink(
        label="External",
        raw_target=target,
        description="External reference.",
        section=None,
        line=2,
    )


def test_percent_encoded_external_hostname_is_decoded_for_validation() -> None:
    resolved = resolve_link(
        "docs/index.md",
        external_link("https://example%2ecom/spec"),
        {},
    )

    assert resolved == {
        "kind": "external",
        "target": "https://example%2ecom/spec",
        "fragment": None,
    }


@pytest.mark.parametrize(
    "target",
    [
        "https://example%ZZcom/spec",
        "https://example%2fcom/spec",
        "https://example%00com/spec",
    ],
)
def test_malformed_or_forbidden_percent_encoded_hosts_fail_closed(target: str) -> None:
    with pytest.raises(IndexNavigationError, match="malformed external link"):
        resolve_link("docs/index.md", external_link(target), {})


def test_escaped_label_bracket_uses_later_real_terminator() -> None:
    parsed = parse_index(
        "# Docs\n\n* [Guide \\] advanced](overview.md) - Read overview.\n",
        "docs/index.md",
    )

    assert len(parsed.links) == 1
    assert parsed.links[0].label == "Guide ] advanced"
    assert parsed.links[0].raw_target == "overview.md"
