# Composition installer release

This directory records the immutable publication identities for the installable Composition Agent Skill. It is a release-publication surface, not the installed skill's runtime authority.

The stable publication deliberately separates three full-SHA identities:

- **installer script revision** `677dc68fe35fc285638b46685950d31e3a3d3c2f` — the remotely executed stdlib-only bootstrap script;
- **skill source revision** `69af2ed811875f95838bf978ee09365554405664` — the `skills/composition/` tree downloaded and atomically installed by that bootstrap script; and
- **stable Composition toolchain revision** `16d3eb411729a79549dbaaf6dab1d05207f83415` — the exact Composer source selected by the installed skill's `runtime-manifest.json`.

The published installer bytes are additionally pinned by SHA-256: `134fae0e01d1ee1d560f5f2c0284dc56e241626fd4d89a426a68fa41d7e93e34`.

`composition-installer.json` is the machine-readable authority for these identities and the installer digest. `scripts/verify_composition_skill_installer_release.py` verifies the descriptor against repository history, the pinned installer bytes, the complete runnable Skill distribution, the complete snapshot-aware toolchain surface, the runtime-lock digest, and strict ancestry between the three immutable revisions.

This skill-source release includes the read-only `doctor` command. For normal consumers, doctor reports CPython support, the selected immutable revision, Git as not required, ephemeral full-SHA source acquisition, and persistent validated runtime-cache readiness without acquiring source/runtime state from the network. `doctor` is diagnostic only and does not replace Composition validation or guarantee later GitHub/package-source availability.

## Agent bootstrap

A coding agent should treat `composition-installer.json` as data rather than assuming a particular download utility. It may use any available HTTPS transport to fetch the installer at the descriptor's immutable repository/revision/path, but it should verify the downloaded bytes against `installer.sha256` before execution. Save the verified installer to a temporary file, execute it with the supported CPython interpreter in isolated mode (`python -I <installer> <target>`), and remove the temporary installer afterward. Neither `curl` nor `wget` nor a templates clone is required by this contract.

The target may be a persistent Agent Skills directory when the host exposes one, or an OS temporary directory for a transient invocation. In either case the installed Composition Skill remains the repository-facing interface and owns `doctor`, `provenance`, `inspect`, `plan`, `apply`, and `validate`.

## Immutable one-line installation

For interactive users who prefer a compact command, install the published skill with an installer URL pinned to the installer script revision:

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/677dc68fe35fc285638b46685950d31e3a3d3c2f/scripts/install_composition_skill.py', timeout=30).read())" /path/to/agent-skills/composition
```

The machine-oriented bootstrap above is preferred when the caller can verify the published digest before execution. For an existing Composition skill installation, append `--replace`. Replacement remains guarded by the local skill installer and is accepted only when the destination is already identified as this skill.

The commands and bootstrap protocol above never execute the mutable `composition` branch or a tag and do not require a templates clone. Normal Composer invocations obtain the selected full-SHA GitHub archive into an OS temporary directory, verify the snapshot inventory while executing, and remove the source snapshot afterward. The validated Python runtime cache remains a separate persistent performance optimization.
