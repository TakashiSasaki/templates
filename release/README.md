# Composition installer release

This directory records the immutable publication identities for the installable Composition Agent Skill. It is a release-publication surface, not the installed skill's runtime authority.

The stable publication deliberately separates three full-SHA identities:

- **installer script revision** `b862171ed7d8fb7f53cb5a28a0d89eab07ab534e` — the remotely executed stdlib-only bootstrap script;
- **skill source revision** `dee6278c275d4c480373acd5b66cfc2c2db4c663` — the `skills/composition/` tree downloaded and atomically installed by that bootstrap script; and
- **stable Composition toolchain revision** `1e8fd592d82670c3d524d5038b8045715bb01038` — the exact Composer source selected by the installed skill's `runtime-manifest.json`.

The published installer bytes are additionally pinned by SHA-256: `161b9fb7f432eec8cb104f4f49d945c7f8ef5654382fb4607a13ae0de5015cc4`.

`composition-installer.json` is the machine-readable authority for these identities and the installer digest. `scripts/verify_composition_skill_installer_release.py` verifies the descriptor against repository history, the pinned installer bytes, the complete runnable Skill distribution, the complete snapshot-aware toolchain surface, the runtime-lock digest, and strict ancestry between the three immutable revisions.

This skill-source release includes the read-only `doctor` command. For normal consumers, doctor reports CPython support, the selected immutable revision, Git as not required, ephemeral full-SHA source acquisition, and persistent validated runtime-cache readiness without acquiring source/runtime state from the network. `doctor` is diagnostic only and does not replace Composition validation or guarantee later GitHub/package-source availability.

## Agent bootstrap

A coding agent should treat `composition-installer.json` as data rather than assuming a particular download utility. It may use any available HTTPS transport to fetch the installer at the descriptor's immutable repository/revision/path, but it must verify the downloaded bytes against `installer.sha256` before execution. Save the verified installer to a temporary file, execute it with the supported CPython interpreter in isolated mode (`python -I <installer> <target>`), and remove the temporary installer afterward. A digest mismatch must terminate before the installer bytes are written or executed. Neither `curl` nor `wget` nor a templates clone is required by this contract.

The target may be a persistent Agent Skills directory when the host exposes one, or an OS temporary directory for a transient invocation. In either case the installed Composition Skill remains the repository-facing interface and owns `doctor`, `provenance`, `inspect`, `plan`, `apply`, and `validate`.

## Verified installation

For interactive users, use the same verify-before-execute invariant. The following POSIX-shell command needs only a supported CPython interpreter. It downloads the immutable installer, verifies the published SHA-256 in memory, prints the verified digest as audit evidence, and only then writes and executes a temporary installer in isolated mode:

```sh
python -I -c '
import hashlib
import pathlib
import subprocess
import sys
import tempfile
import urllib.request

url = "https://raw.githubusercontent.com/TakashiSasaki/templates/b862171ed7d8fb7f53cb5a28a0d89eab07ab534e/scripts/install_composition_skill.py"
expected = "161b9fb7f432eec8cb104f4f49d945c7f8ef5654382fb4607a13ae0de5015cc4"
data = urllib.request.urlopen(url, timeout=30).read()
actual = hashlib.sha256(data).hexdigest()
if actual != expected:
    raise SystemExit(f"installer SHA-256 mismatch: expected {expected}, got {actual}")
print(f"Verified Composition installer SHA-256: {actual}")
with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as handle:
    handle.write(data)
    installer = pathlib.Path(handle.name)
try:
    subprocess.run([sys.executable, "-I", str(installer), *sys.argv[1:]], check=True)
finally:
    installer.unlink(missing_ok=True)
' /path/to/agent-skills/composition
```

For an existing Composition skill installation, append `--replace`. Replacement remains guarded by the local skill installer and is accepted only when the destination is already identified as this skill. Do not replace this command with `exec(urlopen(...).read())`: pinning a URL to a full commit SHA does not by itself verify that the bytes received match the published installer digest.

The commands and bootstrap protocol above never execute the mutable `composition` branch or a tag and do not require a templates clone. Normal Composer invocations obtain the selected full-SHA GitHub archive into an OS temporary directory, verify the snapshot inventory while executing, and remove the source snapshot afterward. The validated Python runtime cache remains a separate persistent performance optimization.
