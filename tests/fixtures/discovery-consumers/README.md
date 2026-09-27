# Fixed Stage A consumer inputs

These JSON files are **test data**, not operational adapters or instructions.
`files` contains unmodified UTF-8 source bytes from the five immutable authority
commits named by `revision`; `git_blobs` binds each file to its Git blob identity.
The recorded baseline expected set was obtained by running that authority's actual
adopted standalone CLI against its complete checkout. Tests rerun that same captured
runtime on the bounded fixture and require the same set and clean validation.

`adapter` is a proposed v2 configuration. `proposed_domain_inputs` are proposed
Policy/Modeling source-document manifests, relocated from their old adapter's
explicit source-only document declarations. They require domain ownership and
adoption in Stage B; no existing index defines their membership. `projection` is
Composition's typed member fixture: its unchanged captured Composer validates the
catalog/descriptor/recipe graph and resolves IDs. The fixture harness adds the
publication catalog's explicit asset paths and distinguishes their filesystem
kinds. It does not implement Composition ID-to-path rules. A catalog mutation test
adds a real valid recipe, commits the isolated source, calls that domain resolver
again, rejects the stale projection and verifies the new expected member.

Only source files needed for these input, link/fragment and formal discovery-gate
checks are captured. This is not a complete authority checkout or a claim that all
Composition/Modeling/Integration/Site tests ran in Policy CI. Fixture/distribution
navigation is excluded or delegated deliberately. Candidate previews modify only
temporary directories. The full proposed index texts, initial diagnostics, old/new
sets and classifications are reproducibly emitted by:

```sh
python scripts/qualify_discovery_candidate.py --output /tmp/discovery-preview.json
```

Retrieve an original byte identity with `git show REVISION:PATH` and verify it
with `git rev-parse REVISION:PATH`. The source revisions and blob identities are
fixture provenance, not trusted adoption pins. Refreshing them requires another
explicit real-input capture and evaluation; never substitute current branch names
for these immutable inputs. The captured Composer is reference-only domain code
invoked by tests, not a second Policy implementation or runtime plugin.
