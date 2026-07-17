# Architecture

The system separates policy authorship, compilation, distribution, and enforcement.

- Policy modules are Markdown with YAML front matter.
- Profiles select ordered policy modules.
- `.agent-policy.yml` is the sole semantic configuration entry point in a product repository.
- The compiler creates a deterministic intermediate rule list and renders agent-specific files.
- `.agent-policy.lock` records input and output hashes.
- Machine-enforceable quality requirements remain in project tests and CI rather than natural-language rules alone.
