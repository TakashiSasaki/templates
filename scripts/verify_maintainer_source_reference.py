#!/usr/bin/env python3
"""Validate a maintainer Skill reference against immutable local Git objects.

This is deliberately a read-only source-reference check.  It is not a landing
engine and it never resolves a branch, tag, or consumer-worktree path.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

EXPECTED_REPOSITORY = "TakashiSasaki/templates"
CANONICAL_SOURCE_MANIFEST_PATH = (
    ".agents/skills/land-templates-stack/source.json"
)
CANONICAL_SKILL_PATH = "repository-skills/land-templates-stack/SKILL.md"
CANONICAL_RULE_PATH = "repository-policy/stacked-pr-landing.md"
CANONICAL_PLANNER_PATH = (
    "repository-skills/land-templates-stack/scripts/plan_review_scope.py"
)
CANONICAL_OBSERVER_PATH = (
    "repository-skills/land-templates-stack/scripts/observe_pr_state.py"
)
CANONICAL_OBSERVER_LIBRARY_PATH = (
    "repository-skills/land-templates-stack/scripts/pr_state_observation.py"
)
CANONICAL_RENDERER_PATH = (
    "repository-skills/land-templates-stack/scripts/render_review_artifacts.py"
)
CANONICAL_PUBLISHER_PATH = (
    "repository-skills/land-templates-stack/scripts/publish_review_artifacts.py"
)
CANONICAL_LIVE_ADAPTER_PATH = (
    "repository-skills/land-templates-stack/scripts/live_review_adapter.py"
)
CANONICAL_MAINTAINER_ENTRYPOINT_PATH = (
    "repository-skills/land-templates-stack/scripts/maintain_review_stack.py"
)
CANONICAL_REFERENCE_SOURCE_TRUST = (
    "repository-skills/land-templates-stack/references/source-trust.md"
)
CANONICAL_REFERENCE_FINDING_FAMILY = (
    "repository-skills/land-templates-stack/references/finding-family-closure.md"
)
CANONICAL_REFERENCE_QUALIFICATION = (
    "repository-skills/land-templates-stack/references/qualification-and-evidence.md"
)
CANONICAL_REFERENCE_LANDING = (
    "repository-skills/land-templates-stack/references/landing-and-resume.md"
)
CANONICAL_REFERENCE_MAINTAINER_ENTRYPOINT = (
    "repository-skills/land-templates-stack/references/maintainer-entrypoint.md"
)
CANONICAL_REFERENCE_PATHS = (
    CANONICAL_REFERENCE_SOURCE_TRUST,
    CANONICAL_REFERENCE_FINDING_FAMILY,
    CANONICAL_REFERENCE_QUALIFICATION,
    CANONICAL_REFERENCE_LANDING,
    CANONICAL_REFERENCE_MAINTAINER_ENTRYPOINT,
)
BASE_SOURCE_CLOSURE_PATHS = (CANONICAL_RULE_PATH, CANONICAL_PLANNER_PATH)
OBSERVER_SOURCE_CLOSURE_PATHS = (
    CANONICAL_OBSERVER_PATH,
    CANONICAL_OBSERVER_LIBRARY_PATH,
)
WORKFLOW_SOURCE_CLOSURE_PATHS = (
    CANONICAL_RENDERER_PATH,
    CANONICAL_PUBLISHER_PATH,
    CANONICAL_LIVE_ADAPTER_PATH,
    CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
)
OPTIONAL_SOURCE_CLOSURE_PATHS = (
    OBSERVER_SOURCE_CLOSURE_PATHS + WORKFLOW_SOURCE_CLOSURE_PATHS
)
SOURCE_CLOSURE_PATHS = (
    BASE_SOURCE_CLOSURE_PATHS + OPTIONAL_SOURCE_CLOSURE_PATHS + CANONICAL_REFERENCE_PATHS
)
FULL_SHA = re.compile(r"[0-9a-f]{40}")

CLOSURE_MODULE_NAMES: dict[str, str] = {
    CANONICAL_PLANNER_PATH: "plan_review_scope",
    CANONICAL_OBSERVER_PATH: "observe_pr_state",
    CANONICAL_OBSERVER_LIBRARY_PATH: "pr_state_observation",
    CANONICAL_RENDERER_PATH: "render_review_artifacts",
    CANONICAL_PUBLISHER_PATH: "publish_review_artifacts",
    CANONICAL_LIVE_ADAPTER_PATH: "live_review_adapter",
    CANONICAL_MAINTAINER_ENTRYPOINT_PATH: "maintain_review_stack",
}


class SourceReferenceError(ValueError):
    """Raised when a source reference cannot be proven immutable and exact."""


@dataclass(frozen=True)
class VerifiedBlob:
    """One immutable source file retained with its verified Git identity."""

    repository: str
    revision: str
    path: str
    blob_sha: str
    content: bytes


@dataclass(frozen=True)
class VerifiedSource:
    revision: str
    skill: bytes
    rule: bytes
    skill_blob: str
    rule_blob: str
    closure: dict[str, bytes]


def git_blob_sha(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _git(repo: Path, *arguments: str) -> str:
    environment = os.environ.copy()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        return subprocess.check_output(
            ["git", *arguments],
            cwd=repo,
            env=environment,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except (subprocess.CalledProcessError, OSError) as exc:
        raise SourceReferenceError("immutable Git object is unavailable") from exc


def _git_bytes(repo: Path, *arguments: str) -> bytes:
    environment = os.environ.copy()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        return subprocess.check_output(
            ["git", *arguments], cwd=repo, env=environment, stderr=subprocess.PIPE
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        raise SourceReferenceError("immutable Git object is unavailable") from exc


def _require_blob(repo: Path, revision: str, path: str) -> tuple[str, bytes]:
    object_id = _git(repo, "rev-parse", "--verify", f"{revision}:{path}")
    if FULL_SHA.fullmatch(object_id) is None or _git(repo, "cat-file", "-t", object_id) != "blob":
        raise SourceReferenceError(f"canonical path is not a blob: {path}")
    payload = _git_bytes(repo, "show", f"{revision}:{path}")
    if git_blob_sha(payload) != object_id:
        raise SourceReferenceError(f"canonical blob changed while reading: {path}")
    return object_id, payload


def verify_blob_source(
    source: Mapping[str, object],
    *,
    repo: Path,
    expected_path: str,
) -> VerifiedBlob:
    """Read one declared source only from its exact immutable Git revision."""

    if source.get("repository") != EXPECTED_REPOSITORY:
        raise SourceReferenceError("unexpected source repository")
    revision = source.get("revision")
    if not isinstance(revision, str) or FULL_SHA.fullmatch(revision) is None:
        raise SourceReferenceError("source revision must be a full lowercase SHA")
    path = source.get("path")
    if path != expected_path:
        raise SourceReferenceError(f"unexpected source path: {path}")
    declared_blob = source.get("blob_sha")
    if not isinstance(declared_blob, str) or FULL_SHA.fullmatch(declared_blob) is None:
        raise SourceReferenceError("source blob must be a full lowercase SHA")
    if source.get("trusted") is not True:
        raise SourceReferenceError("source must explicitly identify a trusted source")
    if _git(repo, "cat-file", "-t", revision) != "commit":
        raise SourceReferenceError("source revision must name a commit object")
    actual_blob, content = _require_blob(repo, revision, expected_path)
    if actual_blob != declared_blob:
        raise SourceReferenceError("declared source blob does not match the snapshot")
    return VerifiedBlob(EXPECTED_REPOSITORY, revision, expected_path, actual_blob, content)


def verify_blob_payload(
    source: Mapping[str, object],
    *,
    content: bytes,
    actual_blob: str | None = None,
    expected_path: str,
) -> VerifiedBlob:
    """Verify bytes fetched through another transport against a source binding."""

    if source.get("repository") != EXPECTED_REPOSITORY:
        raise SourceReferenceError("unexpected source repository")
    revision = source.get("revision")
    if not isinstance(revision, str) or FULL_SHA.fullmatch(revision) is None:
        raise SourceReferenceError("source revision must be a full lowercase SHA")
    path = source.get("path")
    if path != expected_path:
        raise SourceReferenceError(f"unexpected source path: {path}")
    declared_blob = source.get("blob_sha")
    if not isinstance(declared_blob, str) or FULL_SHA.fullmatch(declared_blob) is None:
        raise SourceReferenceError("source blob must be a full lowercase SHA")
    if source.get("trusted") is not True:
        raise SourceReferenceError("source must explicitly identify a trusted source")
    computed_blob = git_blob_sha(content)
    if actual_blob is not None and actual_blob != computed_blob:
        raise SourceReferenceError("transport source blob does not match its content")
    if computed_blob != declared_blob:
        raise SourceReferenceError("declared source blob does not match transport content")
    return VerifiedBlob(EXPECTED_REPOSITORY, revision, expected_path, computed_blob, content)


def load_python_module(source: VerifiedBlob, module_name: str) -> ModuleType:
    """Execute already-verified source bytes as an isolated Python module."""

    module = ModuleType(module_name)
    module.__file__ = f"{source.revision}:{source.path}"
    code = compile(source.content, module.__file__, "exec")
    exec(code, module.__dict__)
    return module


def required_source_closure_paths(skill: bytes) -> tuple[str, ...]:
    """Require only the support files referenced by the candidate Skill."""

    required = list(BASE_SOURCE_CLOSURE_PATHS)
    for ref_path in CANONICAL_REFERENCE_PATHS:
        ref_name = Path(ref_path).name.encode("utf-8")
        if ref_name in skill or ref_path.encode("utf-8") in skill:
            if ref_path not in required:
                required.append(ref_path)
    if (
        CANONICAL_OBSERVER_PATH.encode("utf-8") in skill
        or b"observe_pr_state.py" in skill
        or b"qualification-and-evidence.md" in skill
    ):
        required.extend(OBSERVER_SOURCE_CLOSURE_PATHS)
    if (
        CANONICAL_RENDERER_PATH.encode("utf-8") in skill
        or b"render_review_artifacts.py" in skill
        or b"maintainer-entrypoint.md" in skill
    ):
        required.append(CANONICAL_RENDERER_PATH)
    if (
        CANONICAL_PUBLISHER_PATH.encode("utf-8") in skill
        or b"publish_review_artifacts.py" in skill
        or b"maintainer-entrypoint.md" in skill
    ):
        required.append(CANONICAL_PUBLISHER_PATH)
    if (
        CANONICAL_LIVE_ADAPTER_PATH.encode("utf-8") in skill
        or b"live_review_adapter.py" in skill
        or b"maintainer-entrypoint.md" in skill
    ):
        required.append(CANONICAL_LIVE_ADAPTER_PATH)
    if (
        CANONICAL_MAINTAINER_ENTRYPOINT_PATH.encode("utf-8") in skill
        or b"maintain_review_stack.py" in skill
        or b"maintainer-entrypoint.md" in skill
    ):
        required.append(CANONICAL_MAINTAINER_ENTRYPOINT_PATH)
    return tuple(required)


class IsolatedClosureEnvironment:
    """Materialize and execute verified closure modules in an isolated scope.

    Guarantees:
    1. Every executed module is proven identical to the declared Git blob.
    2. Sibling imports between closure modules resolve strictly from verified closure bytes.
    3. Shadowing by local files in consumer worktree or PYTHONPATH is rejected.
    4. sys.modules contamination (preloaded siblings, cross-revision reuse) is prevented.
    5. Cleanup restores caller environment without side effects.
    6. Missing closure dependencies fail closed.
    """

    def __init__(
        self,
        verified: VerifiedSource,
        *,
        root_dir: Path | None = None,
        repo: Path | None = None,
    ) -> None:
        self.verified = verified
        self._repo = repo
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._saved_sys_modules: dict[str, ModuleType | None] = {}
        self._loaded_modules: set[str] = set()
        self._closed: bool = False
        if root_dir is None:
            self._temp_dir = tempfile.TemporaryDirectory(prefix="maintainer_closure_")
            self.root = Path(self._temp_dir.name)
        else:
            self.root = root_dir
        try:
            self._materialize()
            self._isolate_sys_modules()
        except Exception:
            self.close()
            raise

    def _discover_git_dir(self) -> Path | None:
        candidates = [self._repo, Path.cwd(), Path(__file__).resolve().parent]
        for candidate in candidates:
            if candidate is None:
                continue
            try:
                out = subprocess.check_output(
                    ["git", "-C", str(candidate), "rev-parse", "--git-dir"],
                    stderr=subprocess.PIPE,
                    text=True,
                ).strip()
                return Path(out).resolve()
            except (subprocess.CalledProcessError, OSError):
                continue
        return None

    def _closure_module_names(self) -> set[str]:
        names: set[str] = set(CLOSURE_MODULE_NAMES.values())
        for path in self.verified.closure:
            stem = Path(path).stem
            names.add(stem)
            names.add(f"templates_{stem}")
            if path in CLOSURE_MODULE_NAMES:
                names.add(CLOSURE_MODULE_NAMES[path])
        return names

    def _isolate_sys_modules(self) -> None:
        for name in self._closure_module_names():
            if name in sys.modules:
                cur = sys.modules[name]
                cur_file = getattr(cur, "__file__", None)
                is_own = False
                if cur_file:
                    try:
                        is_own = Path(cur_file).resolve().is_relative_to(self.root.resolve())
                    except (ValueError, OSError):
                        is_own = False
                if not is_own:
                    if name not in self._saved_sys_modules:
                        self._saved_sys_modules[name] = cur
                    del sys.modules[name]
            else:
                if name not in self._saved_sys_modules:
                    self._saved_sys_modules[name] = None

    def _materialize(self) -> None:
        git_dir = self._discover_git_dir()
        if git_dir is not None:
            git_file = self.root / ".git"
            git_file.write_text(f"gitdir: {git_dir}\n", encoding="utf-8")

        skill_file = self.root / CANONICAL_SKILL_PATH
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_bytes(self.verified.skill)
        if git_blob_sha(self.verified.skill) != self.verified.skill_blob:
            raise SourceReferenceError("materialized skill blob mismatch")

        rule_file = self.root / CANONICAL_RULE_PATH
        rule_file.parent.mkdir(parents=True, exist_ok=True)
        rule_file.write_bytes(self.verified.rule)
        if git_blob_sha(self.verified.rule) != self.verified.rule_blob:
            raise SourceReferenceError("materialized rule blob mismatch")

        for rel_path, content in self.verified.closure.items():
            dest = self.root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            if git_blob_sha(content) != git_blob_sha(dest.read_bytes()):
                raise SourceReferenceError(
                    f"materialized closure blob mismatch: {rel_path}"
                )

    def _verify_provenance(self) -> None:
        for c_name in self._closure_module_names():
            if c_name in sys.modules:
                c_mod = sys.modules[c_name]
                c_file = getattr(c_mod, "__file__", None)
                if not c_file:
                    raise SourceReferenceError(
                        f"closure module '{c_name}' in sys.modules has no __file__"
                    )
                try:
                    c_path = Path(c_file).resolve()
                    rel = c_path.relative_to(self.root.resolve())
                except (ValueError, OSError) as exc:
                    raise SourceReferenceError(
                        f"closure module '{c_name}' was loaded from outside isolated root: {c_file}"
                    ) from exc
                rel_str = str(rel)
                if rel_str in self.verified.closure:
                    if c_path.read_bytes() != self.verified.closure[rel_str]:
                        raise SourceReferenceError(
                            f"closure module '{c_name}' bytes altered on disk: {rel_str}"
                        )
                self._loaded_modules.add(c_name)

    def load_module(self, path: str, module_name: str | None = None) -> ModuleType:
        """Load one closure module from the verified isolated root."""
        if path not in self.verified.closure:
            raise SourceReferenceError(
                f"path '{path}' is not declared in verified closure"
            )
        full_path = self.root / path
        if not full_path.is_file():
            raise SourceReferenceError(f"closure file missing: {path}")

        content = full_path.read_bytes()
        if content != self.verified.closure[path]:
            raise SourceReferenceError(f"closure bytes altered: {path}")

        name = module_name or CLOSURE_MODULE_NAMES.get(path, Path(path).stem)

        self._isolate_sys_modules()

        scripts_dir = str(full_path.parent)
        orig_sys_path = list(sys.path)
        clean_sys_path = [p for p in orig_sys_path if p not in ("", ".", os.getcwd())]
        clean_sys_path.insert(0, scripts_dir)
        sys.path = clean_sys_path

        spec = importlib.util.spec_from_file_location(name, full_path)
        if spec is None or spec.loader is None:
            sys.path = orig_sys_path
            raise SourceReferenceError(f"cannot create module spec for {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self._loaded_modules.add(name)

        try:
            spec.loader.exec_module(module)
            self._verify_provenance()
        except Exception:
            if sys.modules.get(name) is module:
                sys.modules.pop(name, None)
            self._loaded_modules.discard(name)
            raise
        finally:
            sys.path = orig_sys_path
        return module

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        all_closure_names = set(self._loaded_modules) | self._closure_module_names()
        for name in all_closure_names:
            cur = sys.modules.get(name)
            if cur is not None:
                cur_file = getattr(cur, "__file__", None)
                if cur_file:
                    try:
                        if Path(cur_file).resolve().is_relative_to(self.root.resolve()):
                            sys.modules.pop(name, None)
                    except (ValueError, OSError):
                        pass
                else:
                    if name in self._loaded_modules:
                        sys.modules.pop(name, None)
        self._loaded_modules.clear()

        for name, saved_mod in self._saved_sys_modules.items():
            if saved_mod is not None:
                sys.modules[name] = saved_mod
            else:
                sys.modules.pop(name, None)
        self._saved_sys_modules.clear()

        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None

    def run_entrypoint(
        self,
        path_or_name: str = CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
        argv: Sequence[str] | None = None,
    ) -> int:
        """Execute entrypoint module's main(argv) strictly within this isolated scope."""
        if self._closed:
            raise SourceReferenceError("cannot execute entrypoint in closed environment")
        module = self.load_module(path_or_name)
        main_fn = getattr(module, "main", None)
        if not callable(main_fn):
            raise SourceReferenceError(
                f"entrypoint module '{path_or_name}' does not define callable main()"
            )
        return int(main_fn(argv))

    def read_closure_bytes(self, rel_path: str) -> bytes:
        """Read bytes from a materialized closure file, ensuring it exists in verified closure."""
        if self._closed:
            raise SourceReferenceError("cannot read closure file in closed environment")
        if rel_path == CANONICAL_SKILL_PATH:
            expected = self.verified.skill
        elif rel_path == CANONICAL_RULE_PATH:
            expected = self.verified.rule
        elif rel_path in self.verified.closure:
            expected = self.verified.closure[rel_path]
        else:
            raise SourceReferenceError(f"file not in verified closure: {rel_path}")

        full_path = self.root / rel_path
        if not full_path.is_file():
            raise SourceReferenceError(f"closure file missing: {rel_path}")
        content = full_path.read_bytes()
        if content != expected:
            raise SourceReferenceError(f"closure bytes altered: {rel_path}")
        return content

    def read_closure_file(self, rel_path: str, encoding: str = "utf-8") -> str:
        """Read text from a materialized closure file, ensuring it exists in verified closure."""
        return self.read_closure_bytes(rel_path).decode(encoding)

    def __enter__(self) -> IsolatedClosureEnvironment:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def load_closure_module(verified: VerifiedSource, path_or_name: str) -> ModuleType:
    """Execute a closure module strictly from verified closure bytes.

    Guarantees that inter-closure imports resolve only to verified closure blobs,
    refusing any shadowing by local files or PYTHONPATH.
    """
    canonical_path = path_or_name
    if canonical_path not in verified.closure:
        for p, m in CLOSURE_MODULE_NAMES.items():
            if m == path_or_name:
                canonical_path = p
                break
        else:
            raise SourceReferenceError(f"unknown closure module: {path_or_name}")

    if canonical_path not in verified.closure:
        raise SourceReferenceError(
            f"module {canonical_path} is not in the verified closure"
        )

    with IsolatedClosureEnvironment(verified) as env:
        return env.load_module(canonical_path)


def run_verified_closure_entrypoint(
    verified: VerifiedSource,
    argv: Sequence[str] | None = None,
    *,
    entrypoint_path: str = CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
    repo: Path | None = None,
) -> int:
    """Materialize verified closure, execute entrypoint main(argv) within isolation, and cleanup."""
    with IsolatedClosureEnvironment(verified, repo=repo) as env:
        return env.run_entrypoint(entrypoint_path, argv)


def load_source_reference_from_trusted_base(
    repo: Path,
    trusted_base_sha: str,
    *,
    manifest_path: str = CANONICAL_SOURCE_MANIFEST_PATH,
) -> dict[str, object]:
    """Read and parse the canonical immutable source reference JSON at a trusted Git base commit."""
    if not isinstance(trusted_base_sha, str) or FULL_SHA.fullmatch(trusted_base_sha) is None:
        raise SourceReferenceError("trusted base SHA must be a full lowercase SHA")
    raw_bytes = _git_bytes(repo, "show", f"{trusted_base_sha}:{manifest_path}")
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:
        raise SourceReferenceError(
            f"cannot parse source manifest at {trusted_base_sha}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise SourceReferenceError("source manifest must be a JSON object")
    return data


def verify_trusted_source_reference(
    source: dict[str, object],
    *,
    repo: Path,
    expected_skill_blob: str | None = None,
    expected_rule_blob: str | None = None,
    expected_planner_blob: str | None = None,
) -> VerifiedSource:
    """Resolve and verify an immutable source reference against local Git objects.

    If expected_planner_blob is omitted, extracts the declared planner blob
    from the manifest's closure for validation against the snapshot.
    """
    planner_blob = expected_planner_blob
    if planner_blob is None:
        closure = source.get("closure")
        if isinstance(closure, list):
            for entry in closure:
                if isinstance(entry, dict) and entry.get("path") == CANONICAL_PLANNER_PATH:
                    blob = entry.get("blob_sha")
                    if isinstance(blob, str) and FULL_SHA.fullmatch(blob):
                        planner_blob = blob
                        break
    if not isinstance(planner_blob, str) or FULL_SHA.fullmatch(planner_blob) is None:
        raise SourceReferenceError(
            "an expected planner blob is required for the adopted source"
        )
    return verify_source_reference(
        source,
        repo=repo,
        expected_skill_blob=expected_skill_blob,
        expected_rule_blob=expected_rule_blob,
        expected_planner_blob=planner_blob,
    )


def verify_source_reference(
    source: dict[str, object],
    *,
    repo: Path,
    expected_skill_blob: str | None = None,
    expected_rule_blob: str | None = None,
    expected_planner_blob: str | None = None,
) -> VerifiedSource:
    """Resolve both canonical files through one exact immutable revision."""

    schema_version = source.get("schema_version")
    if type(schema_version) is not int or schema_version != 2:
        raise SourceReferenceError("source reference must use schema version 2")
    if (
        not isinstance(expected_planner_blob, str)
        or FULL_SHA.fullmatch(expected_planner_blob) is None
    ):
        raise SourceReferenceError(
            "an expected planner blob is required for the adopted source"
        )
    if source.get("kind") != "repository-maintainer-skill-reference":
        raise SourceReferenceError("unsupported source reference kind")
    if source.get("repository") != EXPECTED_REPOSITORY:
        raise SourceReferenceError("unexpected source repository")
    revision = source.get("revision")
    if not isinstance(revision, str) or FULL_SHA.fullmatch(revision) is None:
        raise SourceReferenceError("source revision must be a full lowercase SHA")
    path = source.get("path")
    if path != CANONICAL_SKILL_PATH:
        raise SourceReferenceError("unexpected canonical Skill path")
    declared_skill_blob = source.get("blob_sha")
    if not isinstance(declared_skill_blob, str) or FULL_SHA.fullmatch(declared_skill_blob) is None:
        raise SourceReferenceError("source blob must be a full lowercase SHA")

    if _git(repo, "cat-file", "-t", revision) != "commit":
        raise SourceReferenceError("source revision must name a commit object")
    _git(repo, "cat-file", "-e", f"{revision}^{{commit}}")
    skill_blob, skill = _require_blob(repo, revision, CANONICAL_SKILL_PATH)
    rule_blob, rule = _require_blob(repo, revision, CANONICAL_RULE_PATH)
    if skill_blob != declared_skill_blob:
        raise SourceReferenceError("declared Skill blob does not match the snapshot")
    if expected_skill_blob is not None and skill_blob != expected_skill_blob:
        raise SourceReferenceError("Skill blob does not match the adopted pin")
    if expected_rule_blob is not None and rule_blob != expected_rule_blob:
        raise SourceReferenceError("rule blob does not match the adopted pin")
    closure: dict[str, bytes] = {CANONICAL_RULE_PATH: rule}
    declared_closure = source.get("closure")
    if not isinstance(declared_closure, list):
        raise SourceReferenceError("schema version 2 requires an explicit source closure")
    entries: dict[str, str] = {}
    for item in declared_closure:
        if not isinstance(item, dict):
            raise SourceReferenceError("source closure entries must be objects")
        path = item.get("path")
        blob = item.get("blob_sha")
        if not isinstance(path, str) or path not in SOURCE_CLOSURE_PATHS:
            raise SourceReferenceError("source closure contains an unexpected path")
        if not isinstance(blob, str) or FULL_SHA.fullmatch(blob) is None:
            raise SourceReferenceError("source closure blob must be a full lowercase SHA")
        if path in entries:
            raise SourceReferenceError("source closure contains a duplicate path")
        entries[path] = blob
    required_paths = required_source_closure_paths(skill)
    if set(entries) != set(required_paths):
        raise SourceReferenceError("source closure is incomplete")
    for path, expected_blob in entries.items():
        actual_blob, payload = _require_blob(repo, revision, path)
        if actual_blob != expected_blob:
            raise SourceReferenceError(f"declared closure blob does not match: {path}")
        closure[path] = payload
    if entries[CANONICAL_PLANNER_PATH] != expected_planner_blob:
        raise SourceReferenceError("planner blob does not match the adopted pin")
    return VerifiedSource(revision, skill, rule, skill_blob, rule_blob, closure)
