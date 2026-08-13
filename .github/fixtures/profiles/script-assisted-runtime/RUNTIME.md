# Runtime decision record

## Status

Selection status: SELECTED

## Primary implementation

| Item | Selected value |
|---|---|
| Language | Python |
| Runtime | CPython |
| Minimum runtime version | 3.12 |
| Dependency/package manager | NONE; the helper and tests use only the Python standard library |
| Project manifest | NONE |
| Lockfile policy | NONE |
| Source layout | `scripts/normalize.py` and `tests/test_normalize.py` |
| Supported operating systems | Linux, macOS, and Windows environments with CPython 3.12 or newer |

## Commands

Run every command from the skill root.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | NONE; verify the existing runtime with `python --version` |
| Run in place | `python scripts/normalize.py INPUT OUTPUT` |
| Agent launcher | `python scripts/normalize.py INPUT OUTPUT` |
| Test | `python tests/test_normalize.py` |
| Lint/static analysis | `python -m py_compile scripts/normalize.py` |
| Format check | `python -m py_compile scripts/normalize.py` |
| Build/package | NOT APPLICABLE |

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive containing `SKILL.md`, `RUNTIME.md`, `scripts/normalize.py`, and `tests/test_normalize.py` |
| CLI distribution | NOT APPLICABLE |
| MCP distribution | not supported |
| Human Web interface distribution | not supported |
| Service integration | none |
| Version source of truth | Repository commit containing the skill files |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| NONE | NO | The helper accepts only positional input and output paths | NO |

## Decision rationale

CPython 3.12 or newer is selected because the helper and its executable validation use only standard-library file, encoding, process, and temporary-directory APIs. A separate runtime record is retained to make the supported interpreter, exact invocation, reproducible test command, distribution boundary, and absence of dependencies explicit without promoting the helper to a packaged public CLI or adding unused manifests and lockfiles.
