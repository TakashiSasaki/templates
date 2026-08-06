"""Shared parser and repository model for Skill profile validators."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml


class ParseError(Exception):
    """Raised when a Skill contract cannot be parsed safely."""


class _NoAliasSafeLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects YAML aliases and anchors-by-reference."""

    def compose_node(self, parent, index):  # type: ignore[no-untyped-def]
        if self.check_event(yaml.AliasEvent):
            event = self.peek_event()
            raise yaml.YAMLError(
                f"YAML aliases are not permitted (alias {event.anchor!r})"
            )
        return super().compose_node(parent, index)


class ValuePolicy:
    """Shared scalar-resolution policy used by all validators."""

    _UNRESOLVED_MARKER = re.compile(
        r"^(?:TBD|FIXME|PLACEHOLDER)\.?$", re.IGNORECASE
    )
    _UNRESOLVED_PHRASE = re.compile(
        r"^(?:(?:details?|behavior|contract|implementation|documentation) "
        r"(?:forthcoming|pending|to follow)|to be "
        r"(?:added|decided|determined|defined|documented|specified)|will be "
        r"(?:added|defined|documented|specified)(?: later)?)\.?$",
        re.IGNORECASE,
    )
    _TODO_OR_UNSELECTED = re.compile(r"\b(?:TODO|UNSELECTED)\b", re.IGNORECASE)
    _NOT_CONCRETE = re.compile(
        r"^(?:NONE|NOT (?:SUPPORTED|APPLICABLE))$", re.IGNORECASE
    )
    _NOT_RESOLVED_ALLOWING_UNSUPPORTED = re.compile(
        r"^(?:NONE|NOT APPLICABLE)$", re.IGNORECASE
    )

    @staticmethod
    def strip_backticks(value: object) -> str:
        normalized = str(value).strip()
        if (
            len(normalized) >= 2
            and normalized.startswith("`")
            and normalized.endswith("`")
        ):
            return normalized[1:-1]
        return normalized

    @classmethod
    def unresolved_scalar(cls, value: object) -> bool:
        normalized = re.sub(r"\s+", " ", cls.strip_backticks(value)).strip()
        if not normalized:
            return False
        return bool(
            cls._UNRESOLVED_MARKER.fullmatch(normalized)
            or cls._UNRESOLVED_PHRASE.fullmatch(normalized)
        )

    @classmethod
    def resolved(cls, value: object | None) -> bool:
        if value is None or not str(value).strip():
            return False
        text = str(value)
        return not cls._TODO_OR_UNSELECTED.search(text) and not cls.unresolved_scalar(
            text
        )

    @classmethod
    def concrete(cls, value: object | None) -> bool:
        return cls.resolved(value) and not bool(
            cls._NOT_CONCRETE.fullmatch(cls.strip_backticks(value))
        )

    @classmethod
    def resolved_allow_not_supported(cls, value: object | None) -> bool:
        return cls.resolved(value) and not bool(
            cls._NOT_RESOLVED_ALLOWING_UNSUPPORTED.fullmatch(
                cls.strip_backticks(value)
            )
        )


@dataclass(frozen=True)
class ScalarEntry:
    line_number: int
    kind: str
    value: str
    label: str | None = None


@dataclass
class Declaration:
    path: str
    line_number: int
    fields: dict[str, str] = field(default_factory=dict)


class MarkdownDocument:
    """Line-oriented Markdown helper preserving the Ruby parser's semantics."""

    def __init__(self, text: object, path: str | os.PathLike[str] | None = None):
        self.text = str(text)
        self.path = Path(path) if path is not None else None
        self._lines = self.text.splitlines()

    @classmethod
    def read(cls, path: str | os.PathLike[str]) -> "MarkdownDocument":
        source = Path(path)
        return cls(source.read_text(encoding="utf-8"), path=source)

    @property
    def lines(self) -> list[str]:
        return self._lines

    def section(self, heading: str) -> str | None:
        level_match = re.match(r"^#+", heading)
        if level_match is None:
            raise ValueError(f"heading must begin with '#': {heading!r}")
        level = len(level_match.group(0))
        boundary = re.compile(r"^##\s" if level == 2 else r"^(?:##|###)\s")
        heading_pattern = re.compile(rf"^{re.escape(heading)}\s*$")

        start: int | None = None
        for index, line in enumerate(self.lines):
            if heading_pattern.fullmatch(line):
                start = index + 1
                break
        if start is None:
            return None

        end = len(self.lines)
        for index in range(start, len(self.lines)):
            if boundary.match(self.lines[index]):
                end = index
                break

        body = "\n".join(self.lines[start:end])
        if start < len(self.lines):
            body += "\n"
        return body

    def field(self, label: str, section: str | None = None) -> str | None:
        target = self.text if section is None else str(section)
        match = re.search(rf"^{re.escape(label)}:\s*(.*?)\s*$", target, re.MULTILINE)
        return ValuePolicy.strip_backticks(match.group(1)) if match else None

    def list_field(self, label: str, section: str | None = None) -> str | None:
        target = self.text if section is None else str(section)
        match = re.search(
            rf"^\s*-\s*{re.escape(label)}:\s*(.*?)\s*$", target, re.MULTILINE
        )
        return ValuePolicy.strip_backticks(match.group(1)) if match else None

    def summary_values(self, label: str) -> list[str]:
        values: list[str] = []
        pattern = re.compile(rf"^{re.escape(label)}:\s*(.*?)\s*$")
        for raw_line in self.lines:
            normalized = self._normalize_summary_line(raw_line)
            match = pattern.fullmatch(normalized)
            if match:
                values.append(ValuePolicy.strip_backticks(match.group(1)))
        return values

    def table_rows(self, section: str | None = None) -> list[list[str]]:
        target = self.text if section is None else str(section)
        rows: list[list[str]] = []
        for raw_line in target.splitlines():
            cells = self._parse_table_cells(raw_line.strip())
            if cells is None or not cells:
                continue
            if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                continue
            rows.append([ValuePolicy.strip_backticks(cell) for cell in cells])
        return rows

    def table_value(self, item: str, section: str | None = None) -> str | None:
        for row in self.table_rows(section):
            if row and row[0] == item:
                return row[1] if len(row) == 2 else None
        return None

    def support_values(self) -> list[str]:
        return [
            ValuePolicy.strip_backticks(value)
            for value in re.findall(r"^Supported:\s*(.*?)\s*$", self.text, re.MULTILINE)
        ]

    def declarations(self, label: str) -> list[Declaration]:
        results: list[Declaration] = []
        current: Declaration | None = None
        declaration_pattern = re.compile(rf"^{re.escape(label)}:\s*(.+?)\s*$")
        field_pattern = re.compile(r"^([^:]+):\s*(.*?)\s*$")

        for index, raw_line in enumerate(self.lines, start=1):
            normalized = self._normalize_summary_line(raw_line)
            match = declaration_pattern.fullmatch(normalized)
            if match:
                current = Declaration(
                    path=ValuePolicy.strip_backticks(match.group(1)),
                    line_number=index,
                )
                results.append(current)
                continue

            if current is None:
                continue

            if normalized.startswith("#") or normalized == "```":
                current = None
                continue

            match = field_pattern.fullmatch(normalized)
            if match:
                current.fields[match.group(1).strip()] = ValuePolicy.strip_backticks(
                    match.group(2)
                )

        return results

    def each_scalar(self) -> Iterator[ScalarEntry]:
        for index, raw_line in enumerate(self.lines, start=1):
            normalized = raw_line.strip()
            if not normalized or normalized.startswith("```"):
                continue

            yield ScalarEntry(line_number=index, kind="line", value=normalized)

            field_match = re.fullmatch(
                r"(?:[-*]\s+)?([^|#`][^:]{0,120}?):\s*(.*?)\s*", normalized
            )
            if field_match:
                yield ScalarEntry(
                    line_number=index,
                    kind="field",
                    label=field_match.group(1).strip(),
                    value=field_match.group(2),
                )

            cells = self._parse_table_cells(normalized)
            if cells is None or not cells:
                continue
            if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                continue
            for cell in cells:
                yield ScalarEntry(line_number=index, kind="table", value=cell)

    @staticmethod
    def _normalize_summary_line(line: str) -> str:
        normalized = line.strip()
        if normalized.startswith("- "):
            normalized = normalized[2:].strip()
        return normalized

    @staticmethod
    def _parse_table_cells(line: str) -> list[str] | None:
        if not (line.startswith("|") and line.endswith("|")):
            return None

        cells: list[str] = []
        current: list[str] = []
        escaped = False
        for character in line[1:-1]:
            if character == "|" and not escaped:
                cells.append("".join(current).strip())
                current = []
            else:
                current.append(character)

            if character == "\\":
                escaped = not escaped
            else:
                escaped = False

        cells.append("".join(current).strip())
        return cells


class SkillDocument(MarkdownDocument):
    def __init__(self, text: object, path: str | os.PathLike[str] | None = None):
        super().__init__(text, path=path)
        self.metadata = self._parse_frontmatter()

    @classmethod
    def read(cls, path: str | os.PathLike[str] = "SKILL.md") -> "SkillDocument":
        source = Path(path)
        if not source.is_file():
            raise ParseError(f"Missing universally required file: {source}")
        return cls(source.read_text(encoding="utf-8"), path=source)

    def _display_path(self) -> str:
        return str(self.path) if self.path is not None else "SKILL.md"

    def _parse_frontmatter(self) -> dict[object, object]:
        if not self.lines or self.lines[0] != "---":
            raise ParseError(
                f"{self._display_path()} must begin with YAML frontmatter."
            )

        try:
            closing_index = self.lines.index("---", 1)
        except ValueError as exc:
            raise ParseError(
                f"{self._display_path()} YAML frontmatter must have a closing --- delimiter."
            ) from exc

        source = "\n".join(self.lines[1:closing_index])
        try:
            value = yaml.load(source, Loader=_NoAliasSafeLoader)
        except yaml.YAMLError as exc:
            raise ParseError(
                f"{self._display_path()} YAML frontmatter is invalid: {exc}"
            ) from exc

        if not isinstance(value, dict):
            raise ParseError(
                f"{self._display_path()} YAML frontmatter must be a mapping."
            )
        return value


class ProfileSelection:
    def __init__(self, path: str | os.PathLike[str], profiles: list[str]):
        self.path = Path(path)
        self.profiles = tuple(profiles)

    @classmethod
    def load(
        cls,
        path: str | os.PathLike[str] = "SKILL.md",
        document: MarkdownDocument | None = None,
    ) -> "ProfileSelection":
        effective_document = document or MarkdownDocument.read(path)
        declarations = effective_document.summary_values("Selected profiles")
        if len(declarations) != 1:
            raise ParseError(
                f"{path} must contain exactly one 'Selected profiles:' declaration."
            )

        profiles = [
            profile.strip()
            for profile in declarations[0].split(",")
            if profile.strip()
        ]
        if not profiles:
            raise ParseError(
                f"{path} 'Selected profiles:' must contain at least one non-empty profile tag."
            )

        return cls(path, profiles)

    def template_scaffold(self) -> bool:
        return self.profiles == ("template-scaffold",)

    def selected(self, profile: str) -> bool:
        return profile in self.profiles


class RepositorySnapshot:
    GUIDANCE_ARTIFACT_EXTENSIONS = {
        ".md",
        ".markdown",
        ".mdx",
        ".rst",
        ".adoc",
        ".asciidoc",
        ".txt",
        ".pdf",
    }
    GUIDANCE_ARTIFACT_NAMES = {
        "README",
        "README.md",
        "README.markdown",
        "README.rst",
        "NOTES",
        "NOTES.md",
        "ARCHITECTURE",
        "ARCHITECTURE.md",
        "CONTRIBUTING",
        "CONTRIBUTING.md",
    }

    def __init__(self, root: str | os.PathLike[str] = "."):
        self.root = Path(root).expanduser().resolve()

    def _absolute(self, path: str | os.PathLike[str]) -> Path:
        return self.root / Path(path)

    def file(self, path: str | os.PathLike[str]) -> bool:
        return self._absolute(path).is_file()

    def symlink(self, path: str | os.PathLike[str]) -> bool:
        return self._absolute(path).is_symlink()

    def directory(self, path: str | os.PathLike[str]) -> bool:
        return self._absolute(path).is_dir()

    def document(self, path: str | os.PathLike[str]) -> MarkdownDocument | None:
        absolute = self._absolute(path)
        if not absolute.is_file():
            return None
        return MarkdownDocument.read(absolute)

    def operational_file_present(self, directory: str) -> bool:
        absolute_directory = self._absolute(directory)
        if not absolute_directory.is_dir() or absolute_directory.is_symlink():
            return False

        for current_root, directory_names, file_names in os.walk(
            absolute_directory, followlinks=False
        ):
            current_path = Path(current_root)
            directory_names[:] = [
                name for name in directory_names if not (current_path / name).is_symlink()
            ]
            for name in file_names:
                path = current_path / name
                relative = path.relative_to(self.root).as_posix()
                if relative != f"{directory}/README.md":
                    return True
        return False

    def code_artifact_present(self, directory: str) -> bool:
        absolute_directory = self._absolute(directory)
        if not absolute_directory.is_dir() or absolute_directory.is_symlink():
            return False

        for current_root, directory_names, file_names in os.walk(
            absolute_directory, followlinks=False
        ):
            current_path = Path(current_root)
            directory_names[:] = [
                name for name in directory_names if not (current_path / name).is_symlink()
            ]
            for name in file_names:
                path = current_path / name
                if path.is_symlink() or not path.is_file():
                    continue
                if any(name.casefold() == item.casefold() for item in self.GUIDANCE_ARTIFACT_NAMES):
                    continue
                if path.suffix.lower() in self.GUIDANCE_ARTIFACT_EXTENSIONS:
                    continue
                return True
        return False

    def root_files(self) -> list[str]:
        return [
            child.name
            for child in self.root.iterdir()
            if child.is_file() and not child.is_symlink()
        ]


def support_token(value: object) -> str | None:
    stripped = ValuePolicy.strip_backticks(value)
    parts = re.split(r"[;\s]", stripped, maxsplit=1)
    return parts[0].upper() if parts and parts[0] else None
