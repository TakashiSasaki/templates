# Tests

Replace this file with tests appropriate to the selected runtime.

A concrete skill should cover the following layers as applicable:

1. Domain and application unit tests.
2. CLI parsing, output, stderr, and exit-code tests.
3. MCP tool schema and handler tests.
4. Real stdio subprocess smoke tests.
5. CLI/MCP semantic-equivalence contract tests.
6. Path-boundary, symlink, timeout, and write-safety tests.
7. Skill-structure and instruction-reference checks.
8. End-to-end fixtures representing realistic agent tasks.

Tests should not require an actual language model unless the behavior being evaluated is specifically model selection or instruction triggering.
