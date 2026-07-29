# Scripts and stable launchers

This directory is optional in a concrete skill.

Use it for stable in-place launchers or small deterministic helpers that the skill invokes directly. The selected runtime may instead expose an installed CLI through its normal packaging mechanism.

Rules:

- record every public command in `RUNTIME.md` and `INTERFACES.md`;
- locate the skill root from the launcher location rather than assuming the caller's current directory;
- delegate to reusable implementation code;
- do not duplicate domain logic here;
- do not install runtimes or package managers silently;
- fail with a clear diagnostic when prerequisites are missing;
- preserve the delegated command's exit status.

Delete this directory if the concrete skill has no in-place scripts.
