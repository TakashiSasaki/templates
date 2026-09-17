"""Shared validation of normalized publication URL and text values."""
from __future__ import annotations
import html
import idna
import ipaddress
import re
import string
import unicodedata
from urllib.parse import SplitResult, quote, unquote_to_bytes, urlsplit, urlunsplit
from publication_bundle.identity import BIDIRECTIONAL_CONTROLS

NON_MARKDOWN_LINE_SEPARATORS = frozenset({"\u2028", "\u2029"})


CONTEXTUAL_JOINERS = frozenset({"\u200c", "\u200d"})


FORBIDDEN_DOMAIN_CHARACTERS = frozenset("#/:<>?@[\\]^|%")


IPV4_NUMBER = re.compile(r"\A(?:0[xX][0-9A-Fa-f]*|0[0-7]*|[0-9]+)\Z")


class IndexNavigationError(RuntimeError):
    """Raised when an index navigation graph cannot be produced safely."""


def contains_disallowed_control(
    value: str,
    *,
    allow_layout_whitespace: bool = True,
) -> bool:
    for character in value:
        codepoint = ord(character)
        if (
            (codepoint < 32 and (not allow_layout_whitespace or character not in "\t\n\r"))
            or 0x7F <= codepoint <= 0x9F
            or character in BIDIRECTIONAL_CONTROLS
            or character in NON_MARKDOWN_LINE_SEPARATORS
        ):
            return True
    return False


def parse_ipv4_number(value: str) -> int:
    if value.lower().startswith("0x"):
        return int(value[2:] or "0", 16)
    if len(value) > 1 and value.startswith("0"):
        return int(value[1:] or "0", 8)
    return int(value, 10)


def remove_optional_terminal_empty_part(hostname: str) -> str:
    """Remove at most one terminal dot for WHATWG ends-in-a-number/IPv4 parsing."""
    return hostname[:-1] if hostname.endswith(".") else hostname


def ipv4_ends_in_number(hostname: str) -> bool:
    """Apply the WHATWG ends-in-a-number check to an ASCII host."""
    candidate = remove_optional_terminal_empty_part(hostname)
    if not candidate:
        return False
    last = candidate.rsplit(".", maxsplit=1)[-1]
    if last.isascii() and last.isdigit():
        return True
    return re.fullmatch(r"0[xX][0-9A-Fa-f]*", last) is not None


def validate_browser_ipv4_candidate(
    hostname: str,
    source: str,
    line: int,
    target: str,
) -> bool:
    """Validate WHATWG-style IPv4 candidates; return False for ordinary domains."""
    candidate = remove_optional_terminal_empty_part(hostname)
    if not candidate or not ipv4_ends_in_number(hostname):
        return False
    parts = candidate.split(".")
    if not all(IPV4_NUMBER.fullmatch(part) for part in parts):
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    try:
        numbers = [parse_ipv4_number(part) for part in parts]
    except ValueError as exc:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        ) from exc
    if (
        len(numbers) > 4
        or any(number > 255 for number in numbers[:-1])
        or numbers[-1] >= 256 ** (5 - len(numbers))
    ):
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    return True


def contains_forbidden_domain_codepoint(value: str) -> bool:
    """Return whether an ASCII domain contains a WHATWG-forbidden domain code point."""
    return any(
        ord(character) <= 0x20
        or ord(character) == 0x7F
        or character in FORBIDDEN_DOMAIN_CHARACTERS
        for character in value
    )


def contextual_joiners_are_valid(label: str) -> bool:
    """Validate IDNA ContextJ only where a label actually contains a joiner."""
    for position, character in enumerate(label):
        if character not in CONTEXTUAL_JOINERS:
            continue
        try:
            if not idna.valid_contextj(label, position):
                return False
        except idna.IDNAError:
            return False
    return True


def decode_external_hostname(
    hostname: str,
    source: str,
    line: int,
    target: str,
) -> str:
    """Percent-decode a special-scheme domain before browser-style validation."""
    index = 0
    while index < len(hostname):
        if hostname[index] != "%":
            index += 1
            continue
        if (
            index + 2 >= len(hostname)
            or hostname[index + 1] not in string.hexdigits
            or hostname[index + 2] not in string.hexdigits
        ):
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )
        index += 3
    try:
        decoded = unquote_to_bytes(hostname).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        ) from exc
    if (
        not decoded
        or "%" in decoded
        or any(character.isspace() for character in decoded)
        or contains_disallowed_control(decoded, allow_layout_whitespace=False)
    ):
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    return decoded


def validate_ascii_punycode_labels(
    ascii_hostname: str,
    source: str,
    line: int,
    target: str,
) -> None:
    """Reject malformed or Unicode-invalid existing A-labels."""
    decoded_alabels: list[str] = []
    for label in ascii_hostname.split("."):
        if not label.lower().startswith("xn--"):
            continue
        payload = label[4:]
        if not payload:
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )
        try:
            decoded = payload.encode("ascii").decode("punycode")
            canonical_payload = decoded.encode("punycode").decode("ascii")
            mapped_decoded = idna.uts46_remap(
                decoded,
                std3_rules=False,
                transitional=False,
            )
            mapped_payload = mapped_decoded.encode("punycode").decode("ascii")
        except (UnicodeError, idna.IDNAError) as exc:
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            ) from exc
        if (
            not decoded
            or canonical_payload.lower() != payload.lower()
            or mapped_decoded != decoded
            or mapped_payload.lower() != payload.lower()
            or unicodedata.normalize("NFC", decoded) != decoded
            or unicodedata.category(decoded[0]).startswith("M")
            or not contextual_joiners_are_valid(decoded)
            or contains_disallowed_control(decoded, allow_layout_whitespace=False)
        ):
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )
        decoded_alabels.append(decoded)

    bidi_domain = any(
        unicodedata.bidirectional(character) in {"R", "AL", "AN"}
        for label in decoded_alabels
        for character in label
    )
    if bidi_domain:
        for label in decoded_alabels:
            try:
                idna.check_bidi(label, check_ltr=True)
            except idna.IDNAError as exc:
                raise IndexNavigationError(
                    f"malformed external link in {source}:{line}: {target!r}"
                ) from exc


def validate_whatwg_unicode_labels(
    mapped: str,
    source: str,
    line: int,
    target: str,
) -> list[str]:
    """Apply UTS #46 validity criteria not enforced by mapping alone."""
    labels = mapped.split(".")
    semantic_end = len(labels)
    while semantic_end and not labels[semantic_end - 1]:
        semantic_end -= 1
    semantic_labels = [label for label in labels[:semantic_end] if label]
    if not semantic_labels:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    bidi_domain = any(
        unicodedata.bidirectional(character) in {"R", "AL", "AN"}
        for label in semantic_labels
        for character in label
    )
    for label in semantic_labels:
        if (
            unicodedata.normalize("NFC", label) != label
            or unicodedata.category(label[0]).startswith("M")
            or not contextual_joiners_are_valid(label)
        ):
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )
        if bidi_domain:
            try:
                idna.check_bidi(label, check_ltr=True)
            except idna.IDNAError as exc:
                raise IndexNavigationError(
                    f"malformed external link in {source}:{line}: {target!r}"
                ) from exc
    return labels


def canonicalize_whatwg_domain(
    hostname: str,
    source: str,
    line: int,
    target: str,
) -> str:
    """Map a non-ASCII special-scheme domain with WHATWG-compatible UTS #46 rules."""
    if hostname.isascii():
        return hostname.lower()
    try:
        mapped = idna.uts46_remap(
            hostname,
            std3_rules=False,
            transitional=False,
        )
    except idna.IDNAError as exc:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        ) from exc
    if not mapped:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )

    labels = validate_whatwg_unicode_labels(mapped, source, line, target)
    ascii_labels: list[str] = []
    for label in labels:
        if label.isascii():
            ascii_labels.append(label.lower())
            continue
        try:
            payload = label.encode("punycode").decode("ascii").lower()
        except UnicodeError as exc:
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            ) from exc
        ascii_labels.append("xn--" + payload)
    return ".".join(ascii_labels)


def validate_external_location(
    parsed: SplitResult,
    source: str,
    line: int,
    target: str,
) -> None:
    host_port = parsed.netloc.rsplit("@", maxsplit=1)[-1]
    bracketed_host = host_port.startswith("[")
    try:
        hostname = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        ) from exc
    if not hostname:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    if bracketed_host and "%" in hostname:
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
    hostname = decode_external_hostname(hostname, source, line, target)

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if bracketed_host:
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )
    else:
        if bracketed_host and not isinstance(address, ipaddress.IPv6Address):
            raise IndexNavigationError(
                f"malformed external link in {source}:{line}: {target!r}"
            )
        return
    if validate_browser_ipv4_candidate(hostname, source, line, target):
        return

    ascii_hostname = canonicalize_whatwg_domain(hostname, source, line, target)
    if validate_browser_ipv4_candidate(ascii_hostname, source, line, target):
        return
    validate_ascii_punycode_labels(ascii_hostname, source, line, target)
    if not ascii_hostname or contains_forbidden_domain_codepoint(ascii_hostname):
        raise IndexNavigationError(
            f"malformed external link in {source}:{line}: {target!r}"
        )
