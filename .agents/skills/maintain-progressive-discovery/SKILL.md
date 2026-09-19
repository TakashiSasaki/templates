---
name: maintain-progressive-discovery
description: Discover, classify, validate, and safely maintain semantic index.md navigation boundaries from authoritative repository inventories.
---

# Maintain progressive discovery

<!--
agent-policy-generated: true
source-skill: maintain-progressive-discovery
DO NOT EDIT DIRECTLY
-->

## Purpose

Maintain semantic `index.md` discovery boundaries from authoritative repository
inventories while preserving the distinction between authored navigation and
deterministic generated output.

## Use when

Use this Skill after a repository opts into the `progressive-discovery` Policy
profile and explicitly selects this Skill, especially when documents,
components, recipes, schemas, policy rules, records, generated documentation,
or publication surfaces change.

## Do not use when

Do not use this Skill to infer an authority's semantic ownership, replace a
curated authored index automatically, expose provider source paths as public
URLs, or mutate a repository whose profile and Skill selection are not both
explicit.

## Canonical authorities

The repository's authoritative inventories, source/generated ownership
declarations, `.agent-policy.yml`, and local adapter are the inputs for a run.
The shared Policy profile defines generic semantics; the repository authority
decides unresolved boundaries and authored navigation content.

## Inputs

Discover the repository revision, existing indexes, authoritative inventories,
publication state, provider-maintenance and consumer-distributed surfaces,
generated targets, closed inventories, curated shortcuts, and explicit
exclusions before planning changes.

## Stop conditions

Stop and report `authority-needed` when ownership is ambiguous, an authored
index would need destructive rewriting, a generated target is authored or
modified, a link is unsafe, or required inventory data cannot be read. Apply
only when the caller explicitly authorizes mutation.

## Evidence to report

Report the dry-run plan, classifications, created/updated/deleted/regenerated
outputs, exclusions and reasons, unresolved decisions, validation results,
expected-document coverage, nested-index reachability, and generated freshness.

The Skill is repository-neutral. Read the repository's `.progressive-discovery.json`
adapter when present; it may declare only local facts such as authoritative
inventory paths, generated-index targets, the root index, closed inventories,
curated shortcut boundaries, and explicit exclusions. It must not redefine the
shared semantics. A curated shortcut says that an ancestor index intentionally
links directly to important descendants; it does not cause the Skill to rewrite
or delete an existing nested authored index.

Run the bundled script from the repository root. In a distributed consumer the
path is under `.agents/skills`; in the Policy source tree it is under `skills`:

```sh
python3 .agents/skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py --root .
```

The default is a dry-run discovery and validation. Use `--format json` for a
machine-readable report. `--apply` is the explicit mutation authorization; it
updates only generated index outputs declared by the adapter and refuses to
overwrite a curated authored index. Run the command again after applying and
require the second report to be idempotent.

The workflow is:

1. discover the repository revision, policy selection, existing indexes,
   authoritative inventories, generated/source ownership, publication presence,
   provider-maintenance versus consumer-distributed surfaces, and exclusions;
2. classify meaningful boundaries as `authored-index-needed`,
   `generated-index-needed`, `index-unnecessary`, or `authority-needed`;
3. present create, update, delete, or regenerate plans without mutating in
   dry-run mode;
4. when `--apply` is explicitly authorized, mutate only declared generated
   outputs and preserve curated content;
5. validate authored grammar, local-link safety and fragments, nested-index
   reachability, expected-document coverage, and generated freshness;
6. report applied changes, exclusions and their reasons, unresolved authority
   decisions, and validation results.

The expected discoverable set comes from authoritative inventory data before it
comes from existing indexes. An existing index is not proof that a boundary is
still meaningful. A physical directory with one deep important document may be
skipped in favor of a direct link, and an adapter can record an intentional
curated shortcut when several deep documents are routed by an ancestor index. A
consumer without a publication system is valid; do not invent publication
metadata to satisfy the Skill.

The script is intentionally conservative about authored indexes. To change
curated navigation, make that source change explicitly and rerun validation;
the Skill can identify the missing or stale boundary without destroying curated
shortcuts.

For a repository-local adapter, keep validation commands and inventory paths
local. Do not copy this Skill into `repository-skills/` as a competing generic
implementation; enable the immutable Policy-distributed Skill through the
consumer's `.agent-policy.yml`.

## Exit status and mutation limits

Dry-run exits 0 when validation succeeds, even if the report identifies an
update or authority decision; inspect `result` to establish cleanliness. Invalid
validation exits 1. With `--apply`, exit 0 additionally requires
`NO_UPDATE_REQUIRED` and no apply errors. Refused or incomplete apply exits 1;
missing explicit profile/Skill selection exits 2.

Apply checks planned content identity, generated ownership, and tracked/dirty
state both in global preflight and immediately before each target write/delete.
Directory traversal and mutation use descriptor-relative operations without
following symlinks. Apply also requires Linux `renameat2` with
`RENAME_NOREPLACE` and `RENAME_EXCHANGE` for no-clobber removal/restoration and
complete generated-file replacement; unavailable operations refuse apply. Apply
also holds an exclusive advisory lock on the repository root while constructing
and cleaning its operation-private namespace, so cooperating writers cannot
swap a holding directory between creation and identity binding. A parent
path replacement cannot redirect mutation outside the validated directory.
If a later target changes, apply attempts to restore only its own earlier
changes, checking identity and resulting bytes before restoration. Parent
directories created by apply are recorded as `mkdir PATH` and removed in reverse
order only if the same directory remains empty; existing directories and
concurrently added contents are preserved. New parents are identified in the
private namespace before atomic no-replace publication, so a later pathname
replacement cannot be claimed as an operation-created directory. Deleted-file
rollback and generated-file creation likewise complete bytes before publication.
Rollback restores the saved mode with `fchmod` in the private namespace before
publication; process umask cannot alter that mode. Regeneration writes complete
bytes to a private file, exchanges it with the public name, and validates the
detached old inode before removal; a public-name change is restored only when
the public name still contains the operation's replacement. Rollback
regeneration uses the same exchange path and boundary check; it never writes
an earlier inode through a public fd. The holding
directory's inode is captured before its descriptor is opened, and cleanup
first detaches that identity to a fresh operation-private name, re-detaches it
to a second fresh name immediately before `rmdir`, and rechecks the identity.
A replacement observed between those stages is restored or retained without
deletion. A replacement at the holding pathname is retained and reported,
never removed as if it belonged to the operation. Concurrent
edits or recreated paths are preserved and reported as incomplete rollback.
`applied` retains the mutation history and adds `rollback PATH` for each completed
restoration; `apply_errors` reports any residual uncertainty. Refusal still reports
`AUTHORITY_NEEDED` and exits nonzero even when rollback succeeds. These checks
do not provide filesystem-wide atomicity or serialize independent writers to the
same file. Coordinate exclusive access when that guarantee is required; apply is
not a transaction.

Removal atomically detaches a name into a mode-0700 operation-private directory,
then verifies the captured object identity and content before unlink/rmdir. A
replacement at the original public path is never unlinked by that operation.
An unexpected captured object is restored with atomic no-replace rename. If the
public path is occupied again, both objects survive: `applied` records
`retain PATH at RECOVERY_PATH` and `apply_errors` names that recovery location.
Do not delete a reported recovery directory without inspecting its contents.
The same mechanism protects removal of created files/directories during rollback.

## Inventory source closure

Declared inventories must exist and parse successfully. Their repository-source
paths remain expected even when the files are missing. Publication `destination`,
`destination_path`, and `url_path` fields describe output namespaces, not local
source files. An adapter may explicitly assign a declared inventory's path
namespace using `inventory_path_namespaces`: `repository` (the default),
`external` (another authority), or `deployment` (public routes). External and
deployment inventories are still required and parsed; their path values do not
claim files in this checkout. Keep each such decision in the authority's local
surface declarations, and list the local inventory/configuration file itself
in `expected_documents` when it is a discoverable source.

Malformed adapters, unreadable/missing inventories, missing declared documents,
and orphan nested indexes cannot report a clean result. Generated and retired
targets must be canonical repository-relative paths with no symlink component;
validate that boundary during planning and again before mutation.

An exact deterministic generated result is a no-op, including immediately after
creation or regeneration before a Git commit. A no-op does not rewrite dirty or
untracked content. Any actual write or deletion still requires the planned
snapshot, generated ownership, tracking and dirty-state checks at its boundary.
Explicit expected-document declarations must be canonical local paths; generated
and retired targets must be `index.md` files and cannot be both active and retired.

An adapter may declare `authored_index_exclusions` as a mapping from an existing
non-root authored index to expected document paths and nonempty reasons. This
limits that child index's navigation scope, for example when a published reader
index must omit a source-only inventory linked from the authority root. It does
not remove documents from the global expected inventory or root reachability
validation. Unknown expected paths and malformed declarations require authority.

Repository-namespace inventory paths must be canonical before filtering for
supported document types. Unsafe declarations fail closed; absolute HTTP(S)
references remain external references. JSON and YAML mappings reject duplicate
keys, including Policy selection YAML. Generated Markdown encodes link targets
and escapes prose so valid filename punctuation cannot create broken navigation.
Generated ownership requires the exact marker on the first line. A marker quoted
inside authored prose or examples never grants permission to overwrite or retire
the file; planning and mutation-boundary checks use the same placement rule.
Generated specifications accept only `title`, `section`, and `inventory`, plus
`path` in the list form. Unknown fields are rejected before planning.
Generated `inventory` scopes must be arrays of canonical file/directory paths;
a malformed scope never broadens to the whole expected set. Dry-run retirement
also checks tracked and dirty state. After any applied change, `plan` describes
remaining work recomputed from the resulting navigation; `requested_plan` keeps
the original request and `applied` keeps all mutations, including partial work.
A failed Git tracking or status query means state is unknown, not untracked or
clean. Both dry-run and apply refuse mutation until those states can be read,
including creation of a missing target. Initialize a Git repository before
applying generated indexes; dry-run inspection itself remains available.
Git index flags such as assume-unchanged and skip-worktree can hide local edits;
mutation of an existing target requires an ordinary tracked index entry as well
as a successful clean status query. Unreadable or non-UTF-8 generated targets
require authority. Boundary/exclusion paths are validated before any plan is
produced; malformed source declarations never yield actionable output plans.
Policy selection requires PyYAML; an unavailable parser cannot authorize apply.
Generated titles must contain non-whitespace text. Links inside HTML comments, code spans/fences and four-space/tab-indented
code never establish navigation reachability; visible links remain navigable.
The configured active root index cannot be retired. Both generated title and
section headings require nonblank text. Fragment checks exclude comment/code
headings and anchors; explicit anchors must be actual HTML attributes, and
fragment identities match exactly rather than being silently slug-normalized.
Policy selection must pass the canonical schema-2 configuration schema before
it can authorize mutation. Policy render embeds that exact source schema in the
standalone script; consumer-local schemas cannot replace it. PyYAML and
jsonschema are required validation dependencies, and their absence fails closed.
Unexecutable Git queries produce unknown target state rather than a traceback.
Grammar and reachability use the same visible block view; document fragments
support both ATX and setext headings while excluding comment/code examples.

`publication_system` is a boolean declaration, not proof of a publication build.
`surface_boundaries` maps authority-owned nonempty names to either arrays of local
file/directory paths or descriptive `{source, consumer}` relations with nonempty
text. Local paths must be canonical, nonsymlink paths that exist (or are declared
pending generated indexes/their parent directories). Descriptive relations may
name immutable external Bundle inputs or deployed outputs; they are not local
path inventories and never establish local document reachability. Surface names
and publication semantics belong to the repository authority, not a shared enum.
These declarations do not replace authoritative expected-document inventories,
closed-inventory exclusions, or the provider's publication-contract validator.
