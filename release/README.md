# Composition installer release

This directory records the immutable publication identities for the installable Composition Agent Skill. It is a release-publication surface, not the installed skill's runtime authority.

The stable publication deliberately separates three full-SHA identities:

- **installer script revision** `08c7c9ac647000b7e7232ad5eda4f0b3506a7675` — the remotely executed stdlib-only bootstrap script;
- **skill source revision** `e8ee87483ea97e6cce8f27e6438d98a5a7c724a7` — the `skills/composition/` tree downloaded and atomically installed by that bootstrap script; and
- **stable Composition toolchain revision** `16d3eb411729a79549dbaaf6dab1d05207f83415` — the exact Composer source selected by the installed skill's `runtime-manifest.json`.

`composition-installer.json` is the machine-readable authority for these identities. `scripts/verify_composition_skill_installer_release.py` verifies the descriptor against repository history, the complete runnable Skill distribution, the complete snapshot-aware toolchain surface, the runtime-lock digest, and strict ancestry between the three immutable revisions.

This skill-source release includes the read-only `doctor` command. For normal consumers, doctor reports CPython support, the selected immutable revision, Git as not required, ephemeral full-SHA source acquisition, and persistent validated runtime-cache readiness without acquiring source/runtime state from the network. `doctor` is diagnostic only and does not replace Composition validation or guarantee later GitHub/package-source availability.

## Immutable one-line installation

Install the published skill with an installer URL pinned to the installer script revision:

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/08c7c9ac647000b7e7232ad5eda4f0b3506a7675/scripts/install_composition_skill.py', timeout=30).read())" /path/to/agent-skills/composition
```

For an existing Composition skill installation, append `--replace`. Replacement remains guarded by the local skill installer and is accepted only when the destination is already identified as this skill.

The command above never executes the mutable `composition` branch or a tag and does not require a templates clone. Normal Composer invocations obtain the selected full-SHA GitHub archive into an OS temporary directory, verify the snapshot inventory while executing, and remove the source snapshot afterward. The validated Python runtime cache remains a separate persistent performance optimization.
