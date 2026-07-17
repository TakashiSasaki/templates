# Contributing

Changes to the policy schema, rule merge semantics, lock-file format, or bootstrap trust model require an architecture decision record.

Before committing:

```bash
python -m pytest
python -m compileall -q src
```

Generated fixtures must be reproducible from committed inputs.
