# Runtime decision record

## Status

Selection status: SELECTED

## Primary implementation

| Item | Selected value |
|---|---|
| Language | Python |
| Runtime | CPython |
| Minimum runtime version | 3.12 |
| Dependency/package manager | pip with PEP 517 packaging |
| Project manifest | `pyproject.toml` |
| Lockfile policy | `requirements-build.lock` pins the complete build-tool input; the package has no runtime dependencies |
| Source layout | `src/text_stat/` with repository-local launcher `bin/text-stat` |
| Supported operating systems | Linux, macOS, and Windows with CPython 3.12 or newer |

## Commands

Run commands from the fixture root.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | `python -m pip install --disable-pip-version-check --no-input --requirement requirements-build.lock` |
| Run in place | `python bin/text-stat INPUT` |
| Agent launcher | `python bin/text-stat` |
| Test | `python tests/test_text_stat.py` |
| Lint/static analysis | `python -m py_compile bin/text-stat src/text_stat/__init__.py src/text_stat/cli.py tests/test_text_stat.py` |
| Format check | `python -m py_compile bin/text-stat src/text_stat/__init__.py src/text_stat/cli.py tests/test_text_stat.py` |
| Build/package | `python -m pip wheel --disable-pip-version-check --no-input --no-deps --no-build-isolation --wheel-dir dist .` |

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive containing the Skill contracts, `pyproject.toml`, `requirements-build.lock`, `bin/`, `src/`, and `tests/` |
| CLI distribution | Python wheel built from `pyproject.toml`; installed command is `text-stat` |
| MCP distribution | NOT SUPPORTED |
| Human Web interface distribution | NOT SUPPORTED |
| Service integration | NONE |
| Version source of truth | `project.version` in `pyproject.toml`, which must equal `text_stat.VERSION` |

### Local package installation and activation

Build the wheel first with the exact `Build/package` command above.

POSIX local installation:

```sh
python -m venv .local/venv
.local/venv/bin/python -m pip install --disable-pip-version-check --no-input --no-index --find-links dist text-stat==1.0.0
. .local/venv/bin/activate
text-stat --version
```

PowerShell local installation:

```powershell
python -m venv .local/venv
.local/venv/Scripts/python.exe -m pip install --disable-pip-version-check --no-input --no-index --find-links dist text-stat==1.0.0
.local/venv/Scripts/Activate.ps1
text-stat --version
```

The activation commands affect only the current shell session. The repository-local fallback `python bin/text-stat` and the installed `text-stat` command delegate to the same `text_stat.cli` implementation.

### Packaged CLI commands

| Purpose | Exact command |
|---|---|
| Human CLI | `text-stat` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| NONE | NO | CLI behavior is selected only by arguments and input bytes | NO |

The CLI performs no network access. Installing the pinned build tools may access the configured Python package index; wheel installation from `dist/` is explicitly offline through `--no-index`.

## Decision rationale

CPython 3.12 provides a portable standard-library implementation for the CLI behavior while `pyproject.toml` supplies a standard packaged command. The fixture has no runtime dependency. Build-tool versions are pinned separately so package construction is reviewable without introducing a runtime lock dependency. The public `text-stat` command, structured-output contract, exit statuses, and caller behavior remain language-neutral.
