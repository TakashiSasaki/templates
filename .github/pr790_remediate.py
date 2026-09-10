from pathlib import Path

SOURCE = Path("scripts/materialize_publication_assets.py")
TESTS = Path("tests/test_materialize_publication_assets_review_followup.py")

text = SOURCE.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one source match, got {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)


replace_once(
    """    excluded_roots: tuple[PurePosixPath, ...] = (),
    untracked_paths: tuple[bytes, ...] | None = None,
) -> str:
""",
    """    excluded_roots: tuple[PurePosixPath, ...] = (),
    untracked_paths: tuple[bytes, ...] | None = None,
    tracked_excluded_roots: tuple[PurePosixPath, ...] | None = None,
) -> str:
""",
)

anchor = "def _provider_git_worktree_fingerprint("
start = text.index(anchor)
idx = text.index("        diff_proc = subprocess.run(", start)
text = (
    text[:idx]
    + """        tracked_roots = (
            excluded_roots if tracked_excluded_roots is None else tracked_excluded_roots
        )
"""
    + text[idx:]
)
start = text.index(anchor)
needle = "*_provider_worktree_pathspecs(excluded_roots),"
idx = text.index(needle, start)
text = text[:idx] + "*_provider_worktree_pathspecs(tracked_roots)," + text[idx + len(needle) :]

replace_once(
    """def _provider_semantic_revision(root: Path) -> str:
    manifest_path = root / "generated" / "composition-playground-publication.json"
    if manifest_path.is_file() and not manifest_path.is_symlink():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("semantic_revision"), str):
                return data["semantic_revision"]
        except Exception:
            pass
    return ""


def _materializer_output_roots(
""",
    """def _provider_semantic_revision(root: Path) -> str:
    manifest_path = root / "generated" / "composition-playground-publication.json"
    if manifest_path.is_file() and not manifest_path.is_symlink():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("semantic_revision"), str):
                return data["semantic_revision"]
        except Exception:
            pass
    return ""


def _assert_semantic_revision(
    root: Path,
    expected: str,
    label: str,
    *,
    boundary: str,
) -> None:
    current = _provider_semantic_revision(root)
    if current != expected:
        raise PublicationMaterializationError(
            f"{label}: provider semantic revision changed {boundary} "
            f"({expected!r} → {current!r}); retry after obtaining stable provider metadata"
        )


def _materializer_output_roots(
""",
)

replace_once(
    """def _materializer_output_roots(
    root: Path,
    version: int,
    source_catalog: Any | None,
) -> tuple[PurePosixPath, ...]:
""",
    """def _materializer_output_roots(
    root: Path,
    version: int,
    source_catalog: Any | None,
    *,
    for_tracked: bool = False,
) -> tuple[PurePosixPath, ...]:
""",
)
replace_once(
    """            candidate = parsed.parent if parsed.parent != PurePosixPath('.') else parsed
""",
    """            candidate = (
                parsed
                if for_tracked
                else (parsed.parent if parsed.parent != PurePosixPath('.') else parsed)
            )
""",
)
replace_once(
    """    generated_root = PurePosixPath("generated")
    if generated_root not in roots:
        roots.append(generated_root)
    return tuple(roots)
""",
    """    if not for_tracked:
        generated_root = PurePosixPath("generated")
        if generated_root not in roots:
            roots.append(generated_root)
    return tuple(roots)
""",
)

replace_once(
    """    pre_run_untracked_paths: tuple[bytes, ...],
    output_roots: tuple[PurePosixPath, ...],
    label: str,
""",
    """    pre_run_untracked_paths: tuple[bytes, ...],
    output_roots: tuple[PurePosixPath, ...],
    tracked_output_roots: tuple[PurePosixPath, ...],
    label: str,
""",
)
replace_once(
    """            excluded_roots=output_roots,
            untracked_paths=current_untracked_paths,
        )
        if current != expected_worktree_fingerprint:
""",
    """            excluded_roots=output_roots,
            untracked_paths=current_untracked_paths,
            tracked_excluded_roots=tracked_output_roots,
        )
        if current != expected_worktree_fingerprint:
""",
)

replace_once(
    """    input_untracked_paths: tuple[bytes, ...] = (),
    output_roots: tuple[PurePosixPath, ...] = (),
) -> tuple[str, dict[str, str]]:
""",
    """    input_untracked_paths: tuple[bytes, ...] = (),
    output_roots: tuple[PurePosixPath, ...] = (),
    tracked_output_roots: tuple[PurePosixPath, ...] = (),
) -> tuple[str, dict[str, str], str]:
""",
)

write_call = """        input_worktree_fingerprint,
        input_untracked_paths,
        output_roots,
        label,
        boundary="""
write_replacement = """        input_worktree_fingerprint,
        input_untracked_paths,
        output_roots,
        tracked_output_roots,
        label,
        boundary="""
if text.count(write_call) != 2:
    raise SystemExit(f"expected two stamp input-state calls, got {text.count(write_call)}")
text = text.replace(write_call, write_replacement)

replace_once(
    """    _assert_materialization_fingerprint(
        root,
        fingerprint,
        label,
        boundary="after output snapshot before materialization stamp commit",
    )
    _atomic_write_json(root / STAMP_FILE, stamp_data)
    return git_worktree_fingerprint, generated_digests
""",
    """    _assert_materialization_fingerprint(
        root,
        fingerprint,
        label,
        boundary="after output snapshot before materialization stamp commit",
    )
    _assert_semantic_revision(
        root,
        semantic_rev,
        label,
        boundary="after output snapshot before materialization stamp commit",
    )
    _atomic_write_json(root / STAMP_FILE, stamp_data)
    return git_worktree_fingerprint, generated_digests, semantic_rev
""",
)

replace_once(
    """        semantic_rev = _provider_semantic_revision(root)
        if semantic_rev and data.get("semantic_revision") != semantic_rev:
            return None
""",
    """        semantic_rev = _provider_semantic_revision(root)
        if data.get("semantic_revision") != semantic_rev:
            return None
""",
)
replace_once(
    """        _assert_materialization_fingerprint(
            root,
            fingerprint,
            label,
            boundary="after output snapshot while accepting materialization stamp",
        )
        return catalog
""",
    """        _assert_materialization_fingerprint(
            root,
            fingerprint,
            label,
            boundary="after output snapshot while accepting materialization stamp",
        )
        _assert_semantic_revision(
            root,
            semantic_rev,
            label,
            boundary="after output snapshot while accepting materialization stamp",
        )
        return catalog
""",
)

replace_once(
    """    output_roots = _materializer_output_roots(
        root,
        version,
        catalog if version == 4 else None,
    )
    pre_run_untracked_paths = _provider_git_untracked_paths(
""",
    """    output_roots = _materializer_output_roots(
        root,
        version,
        catalog if version == 4 else None,
    )
    tracked_output_roots = _materializer_output_roots(
        root,
        version,
        catalog if version == 4 else None,
        for_tracked=True,
    )
    pre_run_untracked_paths = _provider_git_untracked_paths(
""",
)
replace_once(
    """        excluded_roots=output_roots,
        untracked_paths=pre_run_untracked_paths,
    )
    run_fingerprint = _materialization_fingerprint(root, materializer)
""",
    """        excluded_roots=output_roots,
        untracked_paths=pre_run_untracked_paths,
        tracked_excluded_roots=tracked_output_roots,
    )
    run_fingerprint = _materialization_fingerprint(root, materializer)
""",
)

prepare_call = """        pre_run_input_worktree_fingerprint,
        pre_run_untracked_paths,
        output_roots,
        label,
        boundary="""
prepare_replacement = """        pre_run_input_worktree_fingerprint,
        pre_run_untracked_paths,
        output_roots,
        tracked_output_roots,
        label,
        boundary="""
if text.count(prepare_call) != 3:
    raise SystemExit(f"expected three prepare input-state calls, got {text.count(prepare_call)}")
text = text.replace(prepare_call, prepare_replacement)

replace_once(
    """    stamped_worktree_fingerprint, stamped_output_digests = _write_stamp(
""",
    """    (
        stamped_worktree_fingerprint,
        stamped_output_digests,
        stamped_semantic_revision,
    ) = _write_stamp(
""",
)
replace_once(
    """        input_untracked_paths=pre_run_untracked_paths,
        output_roots=output_roots,
    )
""",
    """        input_untracked_paths=pre_run_untracked_paths,
        output_roots=output_roots,
        tracked_output_roots=tracked_output_roots,
    )
""",
)
replace_once(
    """    _assert_materialization_fingerprint(
        root,
        run_fingerprint,
        label,
        boundary="after output snapshot before returning materialization success",
    )
    _remember_success(root, run_fingerprint)
""",
    """    _assert_materialization_fingerprint(
        root,
        run_fingerprint,
        label,
        boundary="after output snapshot before returning materialization success",
    )
    _assert_semantic_revision(
        root,
        stamped_semantic_revision,
        label,
        boundary="after output snapshot before returning materialization success",
    )
    _remember_success(root, run_fingerprint)
""",
)

SOURCE.write_text(text, encoding="utf-8")

tests = TESTS.read_text(encoding="utf-8")
marker = '\nif __name__ == "__main__":\n'
if tests.count(marker) != 1:
    raise SystemExit("test insertion marker not unique")
additions = r'''
    def test_tracked_sibling_of_generated_output_remains_an_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materializer = self.write_v4_provider(root)
            tracked_input = root / "generated" / "input.bin"
            tracked_input.parent.mkdir(parents=True, exist_ok=True)
            tracked_input.write_bytes(b"A")
            materializer.write_text(
                "from __future__ import annotations\n"
                "import argparse\n"
                "from pathlib import Path\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--source-root', type=Path, required=True)\n"
                "args = parser.parse_args()\n"
                "source = args.source_root / 'generated' / 'input.bin'\n"
                "payload = source.read_bytes()\n"
                "out = args.source_root / 'generated' / 'output.bin'\n"
                "out.write_bytes(payload)\n"
                "source.write_bytes(b'B')\n",
                encoding="utf-8",
            )
            self.initialize_git_checkout(root)

            with self.assertRaisesRegex(
                PublicationMaterializationError,
                "worktree changed while the materializer was running",
            ):
                materialize_publication(root, "fixture")

            self.assertEqual(b"A", (root / "generated" / "output.bin").read_bytes())
            self.assertEqual(b"B", tracked_input.read_bytes())
            self.assertFalse((root / STAMP_FILE).exists())

    def test_semantic_revision_is_rechecked_after_output_snapshot_on_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materializer = self.write_v4_provider(root)
            manifest = root / "generated" / "composition-playground-publication.json"
            (root / ".gitignore").write_text(
                "generated/composition-playground-publication.json\n",
                encoding="utf-8",
            )
            materializer.write_text(
                materializer.read_text(encoding="utf-8")
                + "manifest = args.source_root / 'generated' / 'composition-playground-publication.json'\n"
                + "manifest.write_text('{\"semantic_revision\": \"A\"}', encoding='utf-8')\n",
                encoding="utf-8",
            )
            self.initialize_git_checkout(root)
            self.assertTrue(materialize_publication(root, "fixture"))
            self.assertTrue(is_publication_materialized(root, "fixture"))

            original = materialization._snapshot_materialized_outputs
            mutated = False

            def mutate_after_output_snapshot(*args, **kwargs):
                nonlocal mutated
                observed = original(*args, **kwargs)
                if not mutated:
                    manifest.write_text('{"semantic_revision": "B"}', encoding="utf-8")
                    mutated = True
                return observed

            with patch.object(
                materialization,
                "_snapshot_materialized_outputs",
                side_effect=mutate_after_output_snapshot,
            ):
                self.assertFalse(is_publication_materialized(root, "fixture"))
            self.assertTrue(mutated)

    def test_semantic_revision_is_rechecked_after_output_snapshot_on_stamp_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            materializer = self.write_v4_provider(root)
            manifest = root / "generated" / "composition-playground-publication.json"
            (root / ".gitignore").write_text(
                "generated/composition-playground-publication.json\n",
                encoding="utf-8",
            )
            materializer.write_text(
                materializer.read_text(encoding="utf-8")
                + "manifest = args.source_root / 'generated' / 'composition-playground-publication.json'\n"
                + "manifest.write_text('{\"semantic_revision\": \"A\"}', encoding='utf-8')\n",
                encoding="utf-8",
            )
            self.initialize_git_checkout(root)
            original = materialization._snapshot_materialized_outputs
            snapshots = 0

            def mutate_during_commit_snapshot(*args, **kwargs):
                nonlocal snapshots
                observed = original(*args, **kwargs)
                snapshots += 1
                if snapshots == 2:
                    manifest.write_text('{"semantic_revision": "B"}', encoding="utf-8")
                return observed

            with patch.object(
                materialization,
                "_snapshot_materialized_outputs",
                side_effect=mutate_during_commit_snapshot,
            ):
                with self.assertRaisesRegex(
                    PublicationMaterializationError,
                    "semantic revision changed after output snapshot before materialization stamp commit",
                ):
                    materialize_publication(root, "fixture")
            self.assertGreaterEqual(snapshots, 2)
            self.assertFalse((root / STAMP_FILE).exists())
'''
tests = tests.replace(marker, "\n" + additions + marker, 1)
TESTS.write_text(tests, encoding="utf-8")
