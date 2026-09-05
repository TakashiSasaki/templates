---
id: pull-request.defer-revision-bound-qualification-until-required
severity: mandatory
overridable: true
order: 958
---
# Defer revision-bound qualification until an authority boundary requires it

A pull-request head or stacked-member commit that exists during dependency-safe construction is a **construction head**: an exact Git identity for the current work state, not automatically a final qualification identity. A **provisional candidate** is a construction state that may continue to change because authorized implementation, upstream dependency work, finding disposition, or other justified mutation is still in progress. A **qualification head** is an intended candidate revision deliberately frozen so required acceptance evidence can bind to that exact revision. A **publication identity** is an immutable revision, digest, artifact, or equivalent identity made authoritative for provenance, release, publication, distribution, or another external consumer boundary.

Until an applicable repository authority or explicit task boundary requires revision-bound acceptance, independent review, provenance, release, publication, merge, or another immutable binding, do not intentionally freeze a provisional candidate solely to acquire final revision-bound evidence or materialize a downstream immutable identity that is expected to follow still-mutable prerequisites. The mere existence of a commit SHA, branch head, or pull request does not by itself establish that the candidate has entered final qualification.

Continue authorized implementation, focused diagnostic validation, pull-request creation, dependency-safe downstream work, and naturally triggered CI while a candidate remains provisional. Do not treat those activities, or an observed successful run on a provisional head, as proof that final qualification has been completed. Do not use this rule to suppress repository-required automatic checks or to substitute focused diagnostics for qualification once an applicable boundary requires it.

When a revision-bound boundary is reached, stabilize the actual prerequisite identities, freeze the intended candidate revision or ordered candidate revisions, and acquire every exact-revision evidence item required by the applicable authority. When provenance, publication, release, generated projection, signed material, or another downstream artifact embeds an upstream exact revision or digest as part of its authoritative meaning, perform that final immutable materialization only after the prerequisite identity is stable enough to bind. If a later justified mutation changes an evidence binding, invalidate and reacquire only the affected revision-bound evidence as required by the applicable evidence rules.

This deferral is an execution-efficiency discipline, not an acceptance waiver. It must not delay an urgent security, operational, data-integrity, or publication-integrity repair, and it must not weaken exact-head CI, independent exact-head review, immutable-head merge protection, release trust, provenance, publication, or other authority-defined completion requirements.
