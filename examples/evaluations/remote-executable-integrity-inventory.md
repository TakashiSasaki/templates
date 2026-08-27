# Remote executable resource integrity inventory

This inventory records remote resources that can cross the boundary from fetched bytes into executable code. It is an audit of the current Composition/Webapp assets, not a new runtime authority.

## Decision

The repository-wide invariant should be:

> A remote resource that is fetched and then executed, imported, or loaded as code requires an immutable identity and verification of the exact bytes received for execution.

The invariant applies to executable resources. It does not require digests for ordinary documentation links, data-only downloads, or locally generated files. An explicit documented exception must record why the resource is outside a product or release trust boundary and what residual risk remains.

“Received-byte verification” means the digest is computed from the byte sequence returned by the acquisition operation, before decoding, text parsing, newline conversion, reserialization, extraction, or execution. A Git revision is an immutable source identity; it is not a substitute for verifying a separately downloaded archive when the archive bytes are the execution input.

## Inventory

| Resource | Role and acquisition | Execution classification | Integrity protection | Assessment |
| --- | --- | --- | --- | --- |
| `scripts/install_composition_skill.py` | Downloads the Composition skill codeload archive at full revision `69af2ed811875f95838bf978ee09365554405664`, verifies the published installer identity/digest where applicable, safely extracts the skill, and installs executable scripts. | downloaded then executed | full Git SHA; installer SHA-256 verification; archive safety checks; no independent archive SHA-256 | Protected for the published installer path. The codeload archive remains an explicit residual risk because archive bytes are not separately digest-pinned. |
| `skills/composition/scripts/runtime_checkout.py` and `run_checkout.py` | Operate the consumer runtime and invoke the locally installed Composition toolchain. They fetch repository history as part of a checkout, but do not download a remote Python file for direct execution. | imported/loaded as executable code (local skill source); remote repository data is not a remote executable helper | skill source full Git SHA through the installer/runtime identity and lock data | Covered by the skill/source identity contract. Repository checkout identity is tracked as runtime/transaction data, not treated as a downloaded script digest. |
| `examples/onboarding/task-ledger/browser_proof.py` | The Webapp walkthrough obtains the helper from a pinned raw GitHub revision, preserves the exact response bytes, verifies the expected SHA-256, writes those bytes, then executes the helper. | downloaded then executed | full Git SHA plus received-byte SHA-256; byte length and execution file are kept identical | Meets the invariant after the byte-preserving acquisition change. |
| `scripts/prepare_chromedriver.py` | Obtains Chrome-for-Testing version metadata and a versioned ChromeDriver archive, extracts the driver, and executes the extracted binary for compatibility checks in CI. | downloaded then executed | versioned/mutable vendor URLs and version matching; no SHA-256 or signed manifest verification | Environment helper outside the published Composition product input. Residual supply-chain risk remains; a targeted future hardening change should add vendor checksum/manifest verification if this helper becomes a release-boundary input. |
| Documentation-only external links | Links in guides and READMEs that a reader may open but that the repository does not fetch and execute as code. | documentation-only | URL only | No executable-resource digest requirement. |
| Contract JSON, schemas, and generated local files | Repository data or locally generated artifacts consumed as data. | data only / generated locally | repository revision, schema validation, or local generation contract as applicable | Do not add executable-resource digests merely because a file is remote-readable or serialized. |

## Classification rules

Use these categories when auditing a new resource:

1. **executed directly** — bytes are invoked as a script or binary.
2. **downloaded then executed** — a remote acquisition produces the execution input.
3. **imported/loaded as executable code** — code is loaded into the process, including a fetched module.
4. **data only** — parsed as data and never treated as code.
5. **documentation-only** — presented as a reader link or example and not acquired by a runtime path.

For categories 1–3, record the source URL, immutable revision or equivalent identity, resource role, capture mode, byte-preserving status, byte length when available, Git blob SHA when applicable, expected/observed digest, and verification result. For categories 4–5, record why execution is impossible or outside the path.

## Follow-up boundary

The inventory does not change the installer revision or published installer SHA-256, and it does not add a generic digest field to every remote file. The two targeted follow-ups are:

- Keep the codeload archive exception visible until archive-level verification or a signed manifest is available.
- Revisit ChromeDriver verification if the CI helper becomes part of a product or release artifact boundary.

A clean-room evaluation should classify a failed digest check caused by text reserialization as an evidence-capture limitation when the published bytes themselves are internally consistent.
