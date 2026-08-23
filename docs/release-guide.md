# Producing a product release

This guide is for consumers of a Composition-managed repository that has selected the release-evidence and release-bundle lifecycle. It explains the normal product-owned path from implemented contract evidence to a revision-bound release handoff.

Composition does not choose your CI provider, package manager, deployment system, secret source, external approval system, signing system, or artifact store. It does provide the repository-local contracts and deterministic producer that bind one exact candidate revision to the proofs that approved it and to the digest-closed contract bundle handed off afterward.

## The normal release sequence

Use this sequence for a product release candidate:

```text
Composition apply / update / upgrade
  -> Composition validate
  -> implement the product
  -> scaffold and complete implementation evidence
  -> define fixed release argv
  -> run product proofs while developing
  -> commit the exact candidate
  -> run produce_release.py for that exact 40-hex commit
  -> validate revision-bound evidence and bundle
  -> perform product-owned packaging / deployment / archival
```

Do not move release production before the candidate commit. The managed release producer deliberately proves an immutable candidate revision rather than whatever bytes happen to be present in a mutable working tree.

## 1. Materialize and validate the repository

Use the normal Composition lifecycle first. For a new repository this means `apply --config ...`; for a managed repository it may mean `apply --mode update` or `apply --mode upgrade --config ...`.

After apply succeeds, run Composition validation before adding product-specific release claims:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

The generated release contracts begin in template mode. Template mode is scaffolding, not evidence that a real product has passed its release gates.

## 2. Complete product implementation evidence

`contracts/implementation-evidence.json` is the authoritative mapping from generated contract targets to product implementation and proof evidence.

For a Web application, start from the deterministic worklist rather than inventing target identifiers manually:

```sh
python scripts/scaffold_webapp_evidence.py
```

The scaffold is non-destructive. Use its records to populate product-mode implementation evidence with:

- the implementation boundary for each required target;
- positive evidence;
- negative evidence where required;
- the authoritative proof `commandId`; and
- the release gate IDs that consume that proof.

The human-readable `command` stored in implementation evidence identifies the proof for review and digest binding. It is not parsed as shell input by the release producer.

Run the implementation-evidence and Webapp evidence validators while filling these records. Product evidence should fail closed until every required target and release gate is covered.

## 3. Define the executable release argv

`contracts/release-execution.json` binds every authoritative implementation-evidence command to the exact executable argument vector and working directory used during release production.

A product-mode entry has this conceptual shape:

```json
{
  "commandId": "product-proof",
  "argv": ["python", "product/prove_product.py"],
  "workingDirectory": "."
}
```

The product owns this argv. Composition executes the array directly; it does not parse the human-readable command through a shell. Keep shell syntax, redirection, interpolation, and ambient command rewriting out of the authoritative execution binding unless the product deliberately chooses a shell executable as part of its reviewed argv.

Product-mode release execution must exactly cover the authoritative commands declared by implementation evidence. Missing, duplicate, extra, malformed, or unsafe execution bindings are rejected before release evidence is approved.

## 4. Commit the exact candidate

Before release production, commit every tracked candidate input that the proofs are intended to approve. The revision passed to the producer must be the current repository `HEAD` and must be written as a full lowercase 40-hex commit ID.

The producer verifies the physical candidate around proof execution. Staged changes, modified or deleted tracked inputs, unsafe tracked-path topology, and non-ignored untracked candidate state fail closed. A normal ignored local environment may exist, but it is not claimed as part of the candidate revision. If your product requires hermetic environment identity, define and review that stronger product contract explicitly.

The canonical release-evidence and release-bundle files are lifecycle outputs. They may differ from their committed template or previous-release bytes while all other tracked candidate inputs remain bound to the named revision.

## 5. Produce release evidence and bundle as one transaction

The normal consumer command is:

```sh
python -I .template-composition/release/produce_release.py \
  --revision <40-hex-revision>
```

Python isolated mode (`-I`) is required. Mutable branch names, tags, abbreviated SHAs, uppercase hex, and an omitted revision are not accepted for a normal release run.

The orchestrator performs one repository-local recoverable transaction:

1. acquire the shared release lifecycle lock;
2. recover any previously interrupted release transaction;
3. snapshot the exact pre-operation `contracts/release-evidence.json` and `contracts/release-bundle.json` bytes into durable `.git`-local backups;
4. publish a durable transaction marker;
5. verify the exact candidate and execute the product-owned fixed argv;
6. produce revision-bound release evidence;
7. verify that the evidence stage did not mutate the downstream bundle;
8. produce a digest-closed release bundle from the approved evidence and the active registered contracts;
9. fsync both canonical lifecycle outputs; and
10. remove the transaction marker as the commit point.

On success, release evidence records the exact subject revision, command-definition digests, execution outcomes, release-gate outcomes, provenance, chronology, and approval decision. The release bundle is bound to the same subject revision and digests every active registered contract except itself; it includes the approved release evidence and therefore closes the handoff without a self-reference cycle.

Optional provenance metadata may be supplied with:

```text
--provenance-kind local-run|ci-run|other
--evidence-provenance-id ...
--evidence-provenance-locator ...
--bundle-provenance-id ...
--bundle-provenance-locator ...
```

The default provenance kind is `local-run`. Provider-specific identifiers and locators remain product-owned metadata; they do not change candidate identity or proof semantics.

## 6. Treat proof failure as a rejected release, not as partial output

If a proof fails, the candidate changes during execution, a proof mutates a protected lifecycle output, bundle production fails, or final revision-bound validation fails, the orchestrator restores both canonical lifecycle outputs to their exact pre-operation bytes before releasing the lifecycle lock whenever normal cleanup can run.

A failed proof is therefore not a partially accepted release. Fix the product or its evidence, create the intended candidate revision, and run the release operation again.

Do not edit generated release evidence by hand to turn a failed execution into an approval. Machine-derived command digests, outcomes, timestamps, gate results, chronology, and revision binding are producer-owned facts.

## 7. Recover after an abrupt interruption

If the process is killed or the machine stops after the transaction marker becomes durable, the next normal invocation recovers the previous transaction before starting new release work.

To perform recovery without executing proofs, run:

```sh
python -I .template-composition/release/produce_release.py --recover-only
```

`--recover-only` does not accept `--revision`. Recovery uses the durable marker and digest-verified backups to restore the exact pre-operation evidence and bundle bytes.

Malformed markers, missing or modified backups, symbolic transaction files, and unsafe canonical output paths fail closed. Do not delete or rewrite the `.git`-local release transaction state to bypass recovery validation.

After a successful recovery you may rerun the normal command for the intended exact candidate.

## 8. Rerunning the same approved candidate is supported

The normal orchestrator may be run again for the same exact candidate revision. It reruns the proofs, regenerates release evidence, and rebuilds the bundle while treating both lifecycle outputs as transaction-owned outputs. The previous canonical evidence and bundle are still snapshotted and restored if the rerun fails.

Use the one-command orchestrator for normal release work. The standalone `produce_release_evidence.py` and `produce_release_bundle.py` commands exist for advanced diagnostics and lifecycle maintenance; manually chaining them is not the normal consumer release path.

## 9. Validate the revision-bound outputs

A successful orchestrated run already performs revision-bound validation. When a release workflow wants an explicit independent check, run the managed validators against the same exact revision:

```sh
python .template-composition/validators/validate_release_evidence.py \
  . --expected-revision <40-hex-revision>
python .template-composition/validators/validate_release_bundle.py \
  . --expected-revision <40-hex-revision>
```

The expected revision must be the same immutable candidate that was supplied to `produce_release.py`.

## What Composition proves and what remains product-owned

Composition's release lifecycle proves a repository-local statement: the named candidate revision, authoritative proof definitions, fixed execution bindings, observed proof outcomes, gate decision, and digest-closed active contract set agree according to the managed validators.

It does not by itself prove deployment success, external artifact identity, secret provenance, build-environment hermeticity, signing identity, transparency-log inclusion, or an external human approval. Add separate reviewed product contracts when those properties are required rather than treating them as implicit consequences of release evidence.

For architectural details of the transaction and evidence model, see the generated `docs/architecture/release-evidence.md` and `docs/architecture/release-bundle.md` in a repository that selects these lifecycle components.
