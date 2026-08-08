# Security policy

This project executes code and writes files in target repositories. Security reports should identify the affected command, operating system, Python version, and a minimal reproduction without including credentials or private repository content.

Canonical repository-maintainer safety policy is declared by `.agent-policy.yml` and `repository-policy/toolchain-safety.md`, together with the shared security rules selected by that configuration. Generated `AGENTS.md` and review instructions project those rules; this document is reporting guidance and an explanatory pointer rather than a second normative policy source.

The repository-local safety rule covers target-repository path containment, rejection of `.git` and symbolic-link escapes, immutable bootstrap execution references, and protection against overwriting files that are not established generated outputs. Security-sensitive changes should be evaluated against that canonical rule and its positive and negative-path tests.
