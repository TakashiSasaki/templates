# Stacked workflow empirical regression corpus

This fixture encodes workflow defect classes observed while stabilizing and publishing the corrected Policy stack around pull requests #706-#710. It is deliberately narrower than the general code-review evaluation corpus: these cases describe orchestration, acceptance-evidence acquisition, base movement, and immutable release propagation behavior rather than reviewer defect-detection quality.

The corpus protects five distinctions:

1. incomplete cumulative coverage remains fail-closed but falls back to ordinary per-member exact-head review instead of review-request loops;
2. lower semantic changes invalidate affected downstream identity preparation and should be propagated coherently before expensive downstream review;
3. lower-member merge/base movement is evaluated by binding rather than triggering unconditional upper-head rewriting or all-evidence invalidation;
4. a final whole-stack audit is requested only after every final member head has completed required CI successfully, then checks architecture/dependencies/completeness without becoming implicit lower-member merge evidence; and
5. merge, CI, and Policy release identities remain exact-revision/full-SHA guarded.

`cases.json` is intentionally simple data, not a new evidence schema or acceptance database. `tests/test_stacked_workflow_regression_corpus.py` maps each empirical case back to the existing Policy, orchestration, merge-gate, and release-trust surfaces.
