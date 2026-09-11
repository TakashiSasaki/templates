# Repository topology: selectable consumer structure

Repository topology is the fifth Composition axis: `artifact.*` identifies what
is built, `foundation.*` supplies shared foundations, `capability.*` selects
externally visible behavior, `lifecycle.*` manages change over time, and
`topology.*` declares repository authority, history, and projection structure.

## Select topology independently of the artifact

`topology.hub-and-orphan` is an optional component of the ordinary `skill`,
`webapp`, and `website` recipes. It is not an artifact recipe. Selecting it keeps
the recipe's artifact identity and resolves at most one topology component.
The authoritative descriptor is
`components/topology.hub-and-orphan/component.json` in Composition.

The component materializes `contracts/repository-topology.json`, its schema,
and a validator. This declares an intended consumer repository layout; it does
not demonstrate that Git already implements that layout. Composer does not
create or switch branches, push refs, mutate `.git`, execute arbitrary hooks,
or update remote submodules. Policy and the coding agent inspect actual Git
state and perform separately authorized operations.

## Hub-and-Orphan in a consumer repository

A consumer chooses its Hub through `hub.branch`; `main` is merely the seed
example. Each component has an independent authority history. A component's
branch name equals its submodule mount path, and component namespaces are
non-overlapping leaves. The Hub and component refs must also be compatible with
Git's ref namespace constraints.

The direction of authority is:

1. A component authority branch contains the source of truth.
2. An immutable commit identifies the selected component content.
3. A Hub submodule gitlink selects that exact commit from the same repository.
4. Hub discovery metadata describes those gitlinks.

The Hub never becomes a second component-content authority. Direct edits to
component content in the projection are prohibited. Synchronization is
provider-neutral: GitHub Actions can implement it, but is not part of topology
identity. Stale discovery must not be mistaken for a current projection.
Renames and deletions require coordinated updates to the declaration, refs,
gitlinks, `.gitmodules`, and discovery metadata; Composer provides no automatic
Git migration executor.

## The templates repository has a separate authority model

The existing `TakashiSasaki/templates` authorities are `site`, `composition`,
and `policy`. Their independent histories do not imply adoption of this consumer
topology. This change does not create a `main` Hub or mount those authorities as
self-referencing submodules.

As described in the [authority model](https://github.com/TakashiSasaki/templates/blob/961014d00cb28f5cc3ee5e162b6eae4323df470a/docs/authority-model.md), `site` owns
integration, provider-lock assembly, discovery, and Pages publication.
Composition owns reusable topology semantics; Policy consumes that contract and
owns coding-agent operational procedures. Site documents and integrates their
public interfaces without redefining either authority.

## Machine discovery and publication provenance

Site generates `agent.json` and `assets/agent.json`; the public discovery URL is
`/agent.json`. Its task routing identifies Composition as required when selecting
repository topology. `publication-sources.json` records immutable provider
revisions. The generator validates release descriptor structure and renders
matching projections; it does not verify cryptographic authority signatures.

Publication selection, consumer topology declaration, observed Git state, and
permission to mutate are distinct facts. A publication pin is not evidence that
the repository has adopted the published topology.
