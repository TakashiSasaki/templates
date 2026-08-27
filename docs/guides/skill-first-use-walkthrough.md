# Agent Skill first-use walkthrough

This is the canonical first-use walkthrough for creating an Agent Skill with Composition. Follow it from top to bottom if your goal is to create a small reusable agent workflow rather than learn the Composition architecture first.

The example Skill is **Release Note Helper**. It is a knowledge-augmented Skill that helps an agent turn a repository change summary into concise release notes using a repository-owned writing guide. It deliberately does not need an application runtime, CLI, MCP server, browser interface, or headless service.

## 0. What this walkthrough will produce

Create the Skill as a **separate consumer repository**. Do not implement it inside `TakashiSasaki/templates`, and do not clone `TakashiSasaki/templates` merely to use Composition.

```text
TakashiSasaki/templates
        |
        | provides Composition tooling and Skill contracts
        v
your separate release-note-helper repository
```

You will reach this path:

```text
create repository
  ↓
install Composition
  ↓
run local bootstrap doctor
  ↓
create composition.json
  ↓
inspect → plan → review → apply → validate
  ↓
valid Skill scaffold
  ↓
edit consumer-owned SKILL.md
  ↓
add a real references/ resource
  ↓
run concrete-completion check + Skill validation + Composition validation
```

A valid initial scaffold is not yet an operational Skill. The scaffold still contains `template-scaffold` and TODO guidance until you replace it with concrete trigger, workflow, resources, outputs, validation, and safety semantics.

## 1. Create the product repository

**Run**

```sh
mkdir /absolute/path/to/release-note-helper
cd /absolute/path/to/release-note-helper
git init
```

**Expected**

A separate Git repository exists and has no `.template-composition/lock.json` yet.

**Repository change**

Yes. You created the consumer repository itself; Composition has not materialized anything yet. Git is used here because this walkthrough creates an ordinary version-controlled product repository; Git is not a prerequisite of the Composition consumer runner itself.

**Next**

Check the Composition runner prerequisite.

## 2. Check prerequisites

Normal Composition consumption requires CPython 3.11, 3.12, 3.13, or 3.14. Git is not required by the Composition runner, and no templates checkout is required.

**Run**

```sh
python --version
```

**Expected**

Python reports 3.11–3.14.

**Repository change**

None.

**What this means**

The local machine can run the stdlib-only immutable installer and bootstrap the selected Composition source archive. Cold runner execution requires HTTPS access to GitHub; a missing Python runtime cache can also require access to the configured Python package source.

**Next**

Install Composition outside the consumer repository.

## 3. Install Composition

Use the reviewed immutable installer. This example installs the skill at `/absolute/path/to/agent-skills/composition`. The installer digest is part of the stable release contract, so the walkthrough verifies the downloaded bytes before writing or executing them.

**Run**

```sh
python -I -c '
import hashlib
import pathlib
import subprocess
import sys
import tempfile
import urllib.request

url = "https://raw.githubusercontent.com/TakashiSasaki/templates/01c65730afdbd431749ffd00e790ff3c5bd72015/scripts/install_composition_skill.py"
expected = "7c2ed9ae19e331f1042299f7f55014632e0b21cceca7df8a56750b2e222c3194"
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
' /absolute/path/to/agent-skills/composition
```

A digest mismatch exits before installer bytes are written or an installer process is launched. The printed verified digest is useful audit evidence. If that destination already contains this Composition skill, append `--replace`; replacement is refused when the existing directory is not identified as the Composition skill.

**Expected**

`/absolute/path/to/agent-skills/composition/scripts/run.py` exists.

**Repository change**

None in Release Note Helper. The Composition skill and its runtime/validation caches live outside the consumer repository. The selected Composition source is an ephemeral full-SHA archive snapshot and is not retained as a templates checkout.

**What this means**

You now have the normal repository-facing Composition runner. Both the full-SHA installer URL and the published SHA-256 are intentional: immutable identity and downloaded-byte verification are separate checks. Deeper installer/toolchain identity details are in [Using Composition](../consumer-guide.md#immutable-source-snapshots-and-runtime-reuse).

Before first Composer execution, run the installed skill's read-only local doctor:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  doctor
```

**Expected**

The report identifies the selected immutable toolchain revision, CPython support, effective runtime-cache path, and acquisition modes. It reports Git as not required, source acquisition as an ephemeral full-SHA archive, and remote/package-source availability as not probed.

**Repository change**

None. Doctor does not modify Release Note Helper and does not acquire source/runtime state from the network. It probes and cleans up the external runtime cache's write/atomic-rename capability; it does not create a persistent source-cache checkout.

**What this means**

`READY` means the locally observable runner prerequisites do not currently block the normal runner path. It is not Composition validation and does not guarantee that a later cold acquisition can reach GitHub or package indexes. If doctor reports a blocker, fix the stated local prerequisite/cache problem rather than editing Composition lock, transaction, or cache markers.

**Next**

Create the Skill composition intent.

## 4. Create `composition.json`

Release Note Helper needs only the `skill` recipe baseline. A knowledge reference is a Skill-owned resource and does not require an application capability.

Create `/absolute/path/to/release-note-helper/composition.json`:

```json
{
  "schema_version": 1,
  "recipe": "skill",
  "components": {
    "include": [],
    "exclude": []
  },
  "parameters": {}
}
```

The same machine-checked example is stored at `examples/onboarding/release-note-helper/composition.json` in the Composition authority.

Do not add `capability.runtime` merely because an agent will execute this workflow. Application capabilities describe maintained product interfaces/runtime behavior, not the fact that an agent itself runs somewhere.

**Repository change**

Yes. `composition.json` is consumer-authored intent; no scaffold files have been materialized yet.

**Next**

Inspect the target.

## 5. Inspect

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  inspect
```

**Expected**

The JSON output reports `state: "unmanaged"` for the newly created directory.

**Repository change**

None. `inspect` is read-only.

**What this means**

Composition does not currently manage this repository. If you instead see a managed state, use the matching existing-repository workflow in [Using Composition](../consumer-guide.md#check-whether-a-repository-is-managed) rather than treating it as fresh.

**Next**

Plan the initial composition.

## 6. Plan and review

Use an absolute `--config` path so the first-use example does not depend on your process working directory. Relative `--config` values are resolved from the process current working directory, not from `--repository`.

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  plan --config /absolute/path/to/release-note-helper/composition.json
```

**Expected**

The JSON plan reports `operation: "initial"`, resolved Skill/lifecycle components, deterministic `actions`, an empty `conflicts` list, and a `lock_preview`. A fresh repository normally produces `create` actions; byte-identical existing destinations can be `adopt-identical`.

**Repository change**

None. Planning is read-only.

**What this means**

This is the fail-closed review point before mutation. Check the target, intent, actions, and conflicts. Do not proceed until every conflict is understood and resolved.

**Next**

Apply the reviewed plan.

## 7. Apply

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  apply --config /absolute/path/to/release-note-helper/composition.json
```

**Expected**

The JSON result reports `status: "applied"` and `.template-composition/lock.json` as the lock.

**Repository change**

Yes. Composition materializes the Skill scaffold and records ownership in the lock.

**Next**

Validate the uncustomized scaffold once before editing it.

## 8. Validate the scaffold

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  validate
```

**Expected**

The public JSON result reports `status: "valid"`.

**What this means**

The Composition state and Skill scaffold structure are valid. It does **not** mean Release Note Helper is an operational Skill: `SKILL.md` still identifies itself as `template-scaffold` and contains TODO guidance. The Skill validator intentionally permits that initial scaffold sentinel, so a separate concrete-completion check is required later.

**Next**

Check ownership before customizing it.

## 9. Know exactly what you may edit

Read `.template-composition/lock.json`; do not edit the lock itself.

For the basic Skill recipe:

| File | Ownership | Action |
| --- | --- | --- |
| `SKILL.md` | `seed` | **Edit it in place.** This becomes the concrete Skill contract. |
| `README.md` | `seed` | **Edit it in place.** Describe the consumer Skill repository. |
| `AGENTS.md` | `seed` | **Edit in place if useful.** It is consumer-owned after initial composition. |
| `.editorconfig`, `.gitignore`, `LICENSE.template` | `seed` | **Edit in place if needed, but keep the active destination present while it remains in the lock.** Do not delete or rename it merely because seed bytes are consumer-owned. You may add separate consumer files such as `LICENSE`. |
| `.github/workflows/validate-skill.yml` | `managed` | **Do not hand-edit.** Composition owns it. |
| `.github/scripts/validate_skill.py` | `managed` | **Do not hand-edit.** Use it as provided. |
| `docs/index.md`, `docs/architecture.md`, `docs/skill-capability-map.md`, `docs/skill-profiles.md` | `managed` | **Do not hand-edit.** They are provider-owned references. |
| `.template-composition/validate.py` and other managed Composition validation material | `managed` | **Do not hand-edit.** |
| `.template-composition/lock.json` | Composer state | **Do not hand-edit.** Lifecycle operations own it. |
| new `references/`, `assets/`, or `scripts/` files | ordinary consumer content | **Create/edit them normally** when the selected Skill profile requires them. |

`seed` transfers byte ownership to the consumer after initial composition, but an active seed destination is still part of the resolved Composition state and must remain present while listed in the lock. `managed` remains Composition-owned. Paths absent from the lock are ordinary consumer content unless another repository-local authority says otherwise. If you eventually want an active seed path removed or renamed as part of the Composition state, make that an explicit source/upgrade transition rather than deleting it locally and forcing validation around the missing path.

## 10. Turn `SKILL.md` into Release Note Helper

Release Note Helper is **knowledge-augmented**: its workflow depends on one maintained repository reference. Replace the template frontmatter and TODO sections with concrete semantics. A minimal direction is:

```yaml
---
name: release-note-helper
description: Draft concise repository release notes from a supplied change summary or diff, following the repository-owned release-note style reference.
---
```

Make the body explicit about:

- **Use this skill when:** the user asks for release notes/changelog text for repository changes and the relevant changes are available.
- **Do not use this skill when:** the user asks to invent changes, approve a release, or mutate repository/release state.
- **Required inputs:** the change summary/diff plus `references/release-note-style.md`.
- **Workflow:** inspect supplied changes, read the style reference, group user-visible changes, call out breaking/migration implications when evidenced, draft output, verify every claim against the input.
- **Output:** release-note prose only unless the user explicitly asks for a file change.
- **Safety:** read-only by default; never publish a release or change repository state merely because the Skill was invoked.
- **Validation:** every factual release-note claim maps to supplied repository evidence and the result follows the style reference.

In the Operational knowledge section, declare the real reference:

```text
Reference: references/release-note-style.md
Read when: every invocation that drafts release-note text
Provides: release-note structure, tone, and inclusion/exclusion rules
Authority or freshness notes: repository-owned guidance; update deliberately when release style changes
```

Replace the scaffold sentinel with exactly:

```text
Selected profiles: knowledge-augmented
```

Remove unused Assets, Helper scripts, and Public execution interfaces sections if the concrete Skill does not use them. Do not retain template TODOs just to preserve the scaffold shape.

## 11. Add a real consumer-owned resource

Create `references/release-note-style.md`. For example, define rules such as:

```markdown
# Release note style

- Lead with user-visible behavior, not internal implementation detail.
- Group changes under Added, Changed, Fixed, or Removed only when the evidence supports that category.
- State breaking changes and required migration actions explicitly.
- Do not claim performance, security, compatibility, or bug fixes without evidence in the supplied changes.
- Prefer concise bullets; omit empty sections.
```

This file is **ordinary consumer content** because it was not materialized by Composition. The `knowledge-augmented` profile makes the reference semantically relevant; the Skill validator checks that declared resource paths are coherent with the selected profile.

## 12. Check concrete completion, then validate the Skill

The structural Skill validator intentionally accepts the initial `template-scaffold` sentinel, because the freshly materialized scaffold itself is a valid starting state. Before calling this repository an operational Release Note Helper, add an explicit consumer completion gate.

**Run**

```sh
if grep -q 'Selected profiles: template-scaffold' SKILL.md; then
  echo 'SKILL.md still selects template-scaffold' >&2
  exit 1
fi
if grep -q '\bTODO\b' SKILL.md; then
  echo 'SKILL.md still contains template TODO guidance' >&2
  exit 1
fi
```

**Expected**

Both checks pass silently because the sentinel and template TODO guidance were replaced in Section 10.

**What this means**

This explicit consumer gate checks **concrete completion**. It is distinct from the provider's structural Skill validator.

Now run the Skill-specific validator:

```sh
python .github/scripts/validate_skill.py .
```

**Expected**

The validator accepts the concrete frontmatter/profile/resource structure. If it reports an undeclared/missing resource or incompatible profile/resource shape, fix consumer-owned Skill material rather than editing the validator. Do not interpret structural validation alone as proof that the scaffold sentinel was replaced; that is why the explicit completion gate ran first.

Then run the full selected Composition validation.

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/release-note-helper \
  validate
```

**Expected**

The public result reports `status: "valid"`.

**What this means**

The repository now contains a concrete Skill contract and real supporting knowledge whose structure satisfies the selected Skill/Composition contracts. Unlike the initial valid scaffold, this result is paired with the explicit consumer completion gate showing that the scaffold sentinel and TODO semantics were replaced.

## 13. Exercise the Skill behavior

Composition validation checks the repository contract; it does not prove that the instructions produce useful release notes in every agent/runtime.

Exercise at least these cases with the agent environment that will consume the Skill:

1. a small additive change with clear user-visible behavior;
2. a change containing a breaking/migration implication;
3. an internal refactor that should **not** be exaggerated into a user-visible feature;
4. incomplete evidence where the correct behavior is to report uncertainty rather than invent a release-note claim.

Record or automate product-specific evaluation in the consumer repository when the Skill becomes important enough to require regression protection.

## 14. Add capabilities only when the Skill really exposes them

This example remains knowledge-augmented and instruction-driven. If the Skill later gains a maintained helper runtime, packaged CLI, MCP interface, MCP App, standalone browser interface, or headless service, change `composition.json` explicitly and use the corresponding Composition capability.

Do not encode those application interfaces as Skill profile names. Skill profiles describe Skill-specific resource structure; capabilities describe maintained application/runtime/interface behavior.

A deliberate component/intent change belongs to `upgrade`, not an ordinary consumer edit.

## 15. Optional Policy adoption

Policy is independent from Composition. It is not a Skill profile or Composition capability.

If coding agents will maintain the Release Note Helper repository itself, adopt Policy using the [Policy getting-started guide](https://templates.moukaeritai.work/policy/getting-started/) after initial Composition materialization. Composition owns none of `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`.

## 16. Ordinary maintenance

Editing `SKILL.md`, revising `references/release-note-style.md`, adding examples, or improving consumer-owned evaluation is ordinary product work. Run the concrete-completion gate, Skill validator, and Composition validation after relevant changes.

Use Composition `update` when moving unchanged normalized intent to a newer compatible Composition source revision. Use explicit `upgrade` when recipe/components/parameters change or a component-version compatibility boundary requires it. Review plans before either mutation and never hand-edit the Composition lock to force success.

## Completion criteria

First-use success means a human can reach all of these states without reading the architecture first:

- Release Note Helper lives in a separate consumer repository.
- Composition is installed outside it.
- the local `doctor` reports bootstrap/cache readiness without being confused with Composition validation.
- `composition.json` selects the minimal `skill` recipe.
- `inspect -> plan -> review -> apply -> validate` is followed in order.
- `plan` is understood to be read-only.
- concrete seed/managed/ordinary-consumer ownership is understood, including the requirement to keep active seed destinations present while they remain in the lock.
- the explicit concrete-completion gate confirms `SKILL.md` no longer selects `template-scaffold` and contains no template TODO guidance.
- `references/release-note-style.md` is a real declared resource.
- Skill-specific validation and full Composition validation pass.
- the next step is behavioral evaluation of the concrete Skill, not more scaffold archaeology.

For exact lifecycle/recovery rules, use [Using Composition](../consumer-guide.md) and the [Composer reference](../reference/composer.md). For the Skill profile model and artifact/capability boundary, use the managed references materialized into the consumer repository.