# Webapp product walkthrough

This is the canonical first-use walkthrough for creating a Web application with Composition. Follow it from top to bottom if you are new to this repository; you do not need to read the Composition architecture first.

The example product is **Task Ledger**. The minimal reference product below provides a browser UI for creating, listing, completing or reopening, deleting, and filtering tasks, persistent storage, an independently supported HTTP JSON API, and a small `list` / `export` CLI. Its API also supports title updates, but the minimal browser UI does not claim browser title editing.

This walkthrough defines its own deliberately small reference-product scope. Optional task notes and a browser title-edit control are normal consumer-owned extensions, not completion requirements for this walkthrough. If you add either feature, update the consumer-owned contracts, implementation, tests, and evidence together.

Composition supplies contracts, managed validation material, and a deterministic lifecycle. It does not choose the product framework, database, API implementation, deployment platform, or product test system. Python and SQLite appear later only as concrete Task Ledger product decisions.

## 0. What this walkthrough will produce

You will create a **separate product repository** named `task-ledger`. Do not clone `TakashiSasaki/templates` and start implementing Task Ledger inside it. The normal relationship is:

```text
TakashiSasaki/templates
        |
        | provides the Composition tooling and contracts
        v
your separate task-ledger product repository
```

By the first milestone you will have:

```text
a separate product repository
        ↓
Composition installed outside that repository
        ↓
composition.json
        ↓
inspect → plan → review → apply → validate
        ↓
a valid Composition scaffold
        ↓
a clear editing boundary and product-development starting point
```

That first `VALID` scaffold is intentionally **not** a claim that the Web application has been implemented or product-tested. The later sections take the same repository through real product code, product verification, implementation evidence, optional Policy adoption, and normal Composition maintenance.

Command examples below use POSIX shell syntax and absolute placeholder paths such as `/absolute/path/to/task-ledger`. On another shell or operating system, use the equivalent directory-creation commands, but keep the shown Python runner argument semantics. In particular, use absolute paths for the canonical first-use `--repository` and `--config` values so their resolution is unambiguous.

## 1. Create the separate product repository

Choose a normal development location that is **not inside your checkout of `TakashiSasaki/templates`**.

**Run**

```sh
mkdir /absolute/path/to/task-ledger
cd /absolute/path/to/task-ledger
git init
```

**Expected**

- `/absolute/path/to/task-ledger` exists as its own Git repository.
- It does not yet contain `.template-composition/lock.json`.

**Repository change**

Yes. This creates the product repository itself. No Composition material has been added yet.

**What this means**

Task Ledger is the consumer repository. `TakashiSasaki/templates` remains the provider of Composition and Policy authorities; it is not the application repository you are about to implement.

**Next**

Check the two prerequisites used by the Composition runner.

## 2. Check prerequisites

The supported runner prerequisites are Git on `PATH` and CPython 3.11, 3.12, 3.13, or 3.14.

**Run**

```sh
git --version
python --version
```

**Expected**

- Git reports a version and exits successfully.
- Python reports 3.11 through 3.14.

**Repository change**

None.

**What this means**

The local machine can run the supported immutable Composition installer and runner. In a sandbox or CI environment whose normal user cache is not writable, set `COMPOSITION_RUNTIME_CACHE` and `COMPOSITION_VALIDATION_CACHE` to writable directories outside the product repository before the first runner invocation; the full cache guidance is in [Using Composition](../consumer-guide.md#install-and-run-the-composition-skill).

**Next**

Install the published Composition skill outside Task Ledger.

## 3. Install Composition

Normal consumers install the Composition skill through the reviewed immutable installer. Pick an installation directory outside the product repository; this walkthrough uses `/absolute/path/to/agent-skills/composition`.

**Run**

```sh
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/9c1c093fca1e7e47a9974150e7739665ec570f6e/scripts/install_composition_skill.py', timeout=30).read())" /absolute/path/to/agent-skills/composition
```

If that destination already contains an installed Composition skill, use the documented `--replace` path in [Using Composition](../consumer-guide.md#install-and-run-the-composition-skill) rather than deleting or overwriting an arbitrary directory.

**Expected**

`/absolute/path/to/agent-skills/composition/scripts/run.py` exists as the installed repository-facing runner.

**Repository change**

None in Task Ledger. The skill is installed at the separate destination you selected. Later runner and validator cache creation also occurs outside the product repository.

**What this means**

You now have the normal consumer entry point. The full-SHA installer URL is intentional: Composition uses reviewed immutable source identities rather than a mutable branch or tag. You do not need to understand the installer/skill/toolchain SHA roles before continuing; see [Using Composition](../consumer-guide.md#immutable-source-runtime-selection-and-cache-reuse) when you need that trust detail.

**Next**

Create Task Ledger's Composition intent file in the product repository.

## 4. Create `composition.json`

Task Ledger deliberately supports three caller-visible concerns beyond the Webapp baseline:

| Requirement | Selection | Why |
| --- | --- | --- |
| Browser product UI | `webapp` recipe baseline | The Webapp artifact already defines browser surfaces, routes, visible states, viewports, and Web-specific validation. |
| Python process and execution commands | `capability.runtime` | The product has a maintained application runtime. |
| Independent HTTP JSON API | `capability.service` | Non-browser callers may use the API without the browser UI. |
| Maintained `list` / `export` CLI | `capability.cli` | The CLI is a supported caller-visible interface. |

A shared process or port does not merge those caller-visible contracts. Conversely, do not select capabilities merely because implementation code happens to use a process, route, or library internally.

Create `/absolute/path/to/task-ledger/composition.json` with exactly this initial intent:

```json
{
  "schema_version": 1,
  "recipe": "webapp",
  "components": {
    "include": [
      "capability.cli",
      "capability.runtime",
      "capability.service"
    ],
    "exclude": []
  },
  "parameters": {}
}
```

The same machine-checked example is stored in `examples/onboarding/task-ledger/composition.json` in the Composition authority. Recipe dependency closure adds required lifecycle components; do not duplicate those required components in `include` merely to document the closure.

**Expected**

`composition.json` is present at the root of the Task Ledger product repository.

**Repository change**

Yes. `composition.json` is consumer intent that you created. Composition has still not materialized any scaffold files.

**What this means**

You have stated what kind of artifact and externally supported capabilities you want. You have not yet asked Composition to mutate the repository.

**Next**

Inspect the target state.

## 5. Inspect the repository

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  inspect
```

**Expected**

Because you just created the directory and no Composition lock exists, the JSON output contains:

```json
{
  "state": "unmanaged"
}
```

The real output also includes the absolute `target`. If you had run `inspect` before creating the directory, `absent` would also be a normal new-target state.

**Repository change**

None. `inspect` is read-only.

**What this means**

Composition does not currently manage this repository. That is the expected first-use state.

If you instead see `managed-valid`, `managed-invalid`, or `managed-interrupted`, stop treating this as a fresh initial composition. Use the state-specific workflow in [Using Composition](../consumer-guide.md#check-whether-a-repository-is-managed); an interrupted repository must be recovered rather than re-initialized.

**Next**

Plan the initial materialization using the configuration you just created.

## 6. Plan the initial materialization

For the canonical example, use an **absolute** `--config` path.

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --config /absolute/path/to/task-ledger/composition.json
```

**Expected**

The JSON plan contains:

- `operation: "initial"`;
- the normalized `intent`;
- the resolved components;
- an `actions` list, normally dominated by `create` for a fresh repository;
- a `conflicts` list, which should be empty before you proceed; and
- a `lock_preview` showing the state that would be recorded.

A byte-identical pre-existing destination may be reported as `adopt-identical` rather than `create`.

**Repository change**

None. Initial planning is read-only. It does not create the lock or scaffold.

**What this means**

You are looking at the complete deterministic mutation proposal before allowing it to run.

`--config` has an important path rule: a relative path is resolved from the **process current working directory**, not from `--repository`. The absolute path above deliberately avoids requiring you to infer that relationship. The same rule applies to a new `upgrade` that accepts `--config`.

**Next**

Review the plan. Do not jump directly from configuration authoring to `apply`.

## 7. Review the plan

Check the `actions` and `conflicts` fields from the previous command.

Proceed when:

- the target is `/absolute/path/to/task-ledger`;
- the recipe and component intent are the ones you selected;
- every action is understood (`create` or an intentional `adopt-identical` on a fresh target); and
- `conflicts` is empty.

If a conflict exists, resolve why the destination already contains different bytes before applying. Do not rename or delete Composition metadata to make the conflict disappear.

**Repository change**

None. Reviewing a plan is a human decision point, not a mutation step.

**What this means**

`plan` is the fail-closed safety boundary between intent and mutation.

**Next**

Apply exactly the reviewed intent.

## 8. Apply the scaffold

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --config /absolute/path/to/task-ledger/composition.json
```

**Expected**

The JSON result reports `status: "applied"`, `operation: "initial"`, created/adopted destinations, and `lock: ".template-composition/lock.json"`.

**Repository change**

Yes. This is the first Composition command in the walkthrough that materializes the scaffold. Composition writes `.template-composition/lock.json` last, after the planned files have been installed and source-state validation succeeds.

**What this means**

Task Ledger is now a Composition-managed consumer repository. Ownership for each materialized file is recorded in the lock.

**Next**

Validate the scaffold before starting product implementation.

## 9. Validate the scaffold

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  validate
```

**Expected**

The public JSON result has `status: "valid"`. Selected-component checks include the Webapp and lifecycle validators required by the resolved component set. Because implementation evidence starts in `template` mode, the implementation-evidence check is deferred rather than asserted as a product claim.

**Repository change**

No product-repository content is intentionally changed by validation. A cold validation may create or reuse an isolated cache outside the repository.

**What this means**

> **Composition validation: VALID** means the resolved Composition state and template contracts are valid. It does **not** mean that Task Ledger is implemented, product-tested, deployed, or release-ready.

This distinction is the boundary between a safe scaffold and a finished product.

**Next**

Inspect ownership before editing anything generated by Composition.

## 10. Inspect the generated tree and editing boundary

Read `.template-composition/lock.json`. Do not edit the lock itself. It records each materialized file's component owner, ownership mode, and materialized digest.

For this Task Ledger configuration, concrete examples are:

| File | Ownership | What you should do |
| --- | --- | --- |
| `README.md` | `seed` | **Edit it.** Replace scaffold wording with Task Ledger-specific documentation. |
| `TEMPLATE.md` | `seed` | **Edit it.** Specialize the Webapp product contract. |
| `RUNTIME.md` | `seed` | **Edit it.** Record the actual Task Ledger runtime decisions. |
| `CLI_INTERFACE.md` | `seed` | **Edit it.** Define the supported `list` / `export` behavior. |
| `SERVICE_INTERFACE.md` | `seed` | **Edit it.** Define the independently supported JSON API. |
| `contracts/routes.json`, `contracts/surfaces.json`, `contracts/ui-states.json`, `contracts/viewports.json` | `seed` | **Edit them.** Make the browser contracts truthful for Task Ledger. |
| `contracts/implementation-evidence.json` | `seed` | **Edit later, after real proofs exist.** It initially remains in `template` mode. |
| `contracts/manifest.json` | `generated` | **Do not hand-edit it.** Composition regenerates it deterministically. |
| `schemas/*.schema.json` | `managed` | **Do not hand-edit them.** They remain Composition-owned. |
| `.github/workflows/validate-webapp.yml` | `managed` | **Do not hand-edit it.** It is Composition-owned validation wiring. |
| `scripts/validate_contracts.py`, `scripts/scaffold_webapp_evidence.py` and other scaffold validators | `managed` | **Do not hand-edit them.** Use them as provided. |
| `.template-composition/validate.py` and other `.template-composition` validator material | `managed` | **Do not hand-edit them.** |
| `.template-composition/lock.json` | Composer state | **Do not hand-edit it.** Lifecycle operations own it. |
| new files such as `task_ledger/cli.py` or `tests/test_task_ledger.py` | ordinary consumer content | **Create and edit them normally.** They are product implementation, not Composition-owned material. |

The generic rule is: `seed` transfers to consumer ownership after initial materialization; `managed` and `generated` remain Composition-owned; a path absent from the lock is ordinary consumer content unless another repository-local authority says otherwise.

Do not copy a managed schema or validator into a product-owned variant merely to bypass validation.

**Next**

Turn the editable seeds into truthful Task Ledger contracts, then implement the product in ordinary consumer files.

## 11. Replace template assumptions with the actual product contract

Keep only contract items the product really implements.

### Browser contract

A small Task Ledger inventory can use:

| Contract | Product decision |
| --- | --- |
| surface | `primary`: Task Ledger browser UI, local-product audience, non-diagnostic |
| route | `home` at `/`: canonical task-list route |
| states | `ready` plus only the loading/empty/error states actually visible in the implementation |
| viewport | retain or revise the responsive lower bound and input/zoom behavior to match tested behavior |

Do not add authentication, administration, role-based authorization, touch support, multiple breakpoints, or diagnostic surfaces merely because a larger application might need them.

### Runtime contract

Concretize `RUNTIME.md` with consumer decisions. For this example:

```text
Implementation ecosystem: CPython 3.11+
Persistence: SQLite
Server command: python -m task_ledger.cli --database task-ledger.db serve --host 127.0.0.1 --port 8080
Distribution: source execution for this example
```

These are product decisions, not Composition defaults.

### Service contract

Concretize `SERVICE_INTERFACE.md` because the JSON API is independently supported. A small contract can include:

```text
GET    /api/tasks?status=all|open|completed
GET    /api/tasks/{id}
POST   /api/tasks
PATCH  /api/tasks/{id}
DELETE /api/tasks/{id}
GET    /healthz
```

Specify request validation, result/error semantics, size limits, authentication/exposure decisions, readiness/liveness behavior, restart handling, and the relationship to the browser UI. Sharing one process/listener with the UI does not remove those service obligations.

### CLI contract

Concretize `CLI_INTERFACE.md`, for example:

```sh
python -m task_ledger.cli --database task-ledger.db list --status all
python -m task_ledger.cli --database task-ledger.db export
```

Document stdout/stderr, exit status, invalid arguments, persistence-target selection, and whether CLI operations have semantics equivalent to corresponding API operations.

## 12. Create the minimal consumer-owned implementation and tests

Do not stop at a hypothetical tree. The commands below create a small but executable Python/SQLite implementation, browser UI, product tests, and the verifier that Section 13 runs. All of these paths are ordinary consumer content: none is present in the Composition lock.

From `/absolute/path/to/task-ledger`, create the directories first:

```sh
mkdir -p task_ledger/static tests scripts
touch task_ledger/__init__.py
```

Create `task_ledger/cli.py`:

```python
from __future__ import annotations

import argparse
import json
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def connect(database: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE IF NOT EXISTS tasks ("
        "id INTEGER PRIMARY KEY, title TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0)"
    )
    connection.commit()
    return connection


def task_dict(row: sqlite3.Row) -> dict[str, object]:
    return {"id": row["id"], "title": row["title"], "completed": bool(row["completed"])}


def list_tasks(database: str, status: str = "all") -> list[dict[str, object]]:
    if status not in {"all", "open", "completed"}:
        raise ValueError("status must be all, open, or completed")
    query = "SELECT id, title, completed FROM tasks"
    parameters: tuple[object, ...] = ()
    if status != "all":
        query += " WHERE completed = ?"
        parameters = (1 if status == "completed" else 0,)
    query += " ORDER BY id"
    with connect(database) as connection:
        return [task_dict(row) for row in connection.execute(query, parameters)]


def create_task(database: str, title: object) -> dict[str, object]:
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be a non-empty string")
    with connect(database) as connection:
        cursor = connection.execute("INSERT INTO tasks(title) VALUES (?)", (title.strip(),))
        row = connection.execute(
            "SELECT id, title, completed FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    assert row is not None
    return task_dict(row)


def get_task(database: str, task_id: int) -> dict[str, object] | None:
    with connect(database) as connection:
        row = connection.execute(
            "SELECT id, title, completed FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return task_dict(row) if row is not None else None


def update_task(database: str, task_id: int, changes: dict[str, object]) -> dict[str, object] | None:
    current = get_task(database, task_id)
    if current is None:
        return None
    title = changes.get("title", current["title"])
    completed = changes.get("completed", current["completed"])
    if not isinstance(title, str) or not title.strip() or not isinstance(completed, bool):
        raise ValueError("title must be non-empty and completed must be boolean")
    with connect(database) as connection:
        connection.execute(
            "UPDATE tasks SET title = ?, completed = ? WHERE id = ?",
            (title.strip(), int(completed), task_id),
        )
    return get_task(database, task_id)


def delete_task(database: str, task_id: int) -> bool:
    with connect(database) as connection:
        cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return cursor.rowcount == 1


def make_server(database: str, host: str, port: int) -> ThreadingHTTPServer:
    static_root = Path(__file__).with_name("static")

    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status: int, value: object) -> None:
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_json(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            value = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(value, dict):
                raise ValueError("JSON body must be an object")
            return value

        def task_id(self, path: str) -> int | None:
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] == ["api", "tasks"] and parts[2].isdigit():
                return int(parts[2])
            return None

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                self.send_json(HTTPStatus.OK, {"status": "ok"})
                return
            if parsed.path == "/api/tasks":
                status = parse_qs(parsed.query).get("status", ["all"])[0]
                try:
                    self.send_json(HTTPStatus.OK, list_tasks(database, status))
                except ValueError as exc:
                    self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            task_id = self.task_id(parsed.path)
            if task_id is not None:
                task = get_task(database, task_id)
                self.send_json(HTTPStatus.OK, task) if task else self.send_json(
                    HTTPStatus.NOT_FOUND, {"error": "task not found"}
                )
                return
            if parsed.path == "/":
                body = (static_root / "index.html").read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/tasks":
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            try:
                self.send_json(HTTPStatus.CREATED, create_task(database, self.read_json().get("title")))
            except (ValueError, json.JSONDecodeError) as exc:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def do_PATCH(self) -> None:
            task_id = self.task_id(urlparse(self.path).path)
            if task_id is None:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            try:
                task = update_task(database, task_id, self.read_json())
            except (ValueError, json.JSONDecodeError) as exc:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self.send_json(HTTPStatus.OK, task) if task else self.send_json(
                HTTPStatus.NOT_FOUND, {"error": "task not found"}
            )

        def do_DELETE(self) -> None:
            task_id = self.task_id(urlparse(self.path).path)
            if task_id is None or not delete_task(database, task_id):
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "task not found"})
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    subcommands = parser.add_subparsers(dest="command", required=True)
    list_parser = subcommands.add_parser("list")
    list_parser.add_argument("--status", choices=("all", "open", "completed"), default="all")
    subcommands.add_parser("export")
    serve_parser = subcommands.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    if args.command == "list":
        for task in list_tasks(args.database, args.status):
            marker = "x" if task["completed"] else " "
            print(f"{task['id']}\t[{marker}]\t{task['title']}")
        return 0
    if args.command == "export":
        print(json.dumps(list_tasks(args.database), ensure_ascii=False, indent=2))
        return 0

    server = make_server(args.database, args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `task_ledger/static/index.html`:

```html
<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Task Ledger</title>
<h1 id="main-heading">Task Ledger</h1>
<form id="new-task"><input id="title" required><button>Add task</button></form>
<label>Show <select id="status"><option>all</option><option>open</option><option>completed</option></select></label>
<ul id="tasks"></ul>
<p id="message" role="status"></p>
<script>
const tasks = document.querySelector('#tasks');
const message = document.querySelector('#message');
async function request(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  if (!response.ok && response.status !== 204) throw new Error(await response.text());
  return response.status === 204 ? null : response.json();
}
async function load() {
  tasks.replaceChildren();
  const values = await request('/api/tasks?status=' + document.querySelector('#status').value);
  if (!values.length) message.textContent = 'No tasks yet.'; else message.textContent = '';
  for (const task of values) {
    const item = document.createElement('li');
    const label = document.createElement('span');
    label.textContent = task.title + (task.completed ? ' (completed)' : '');
    const toggle = document.createElement('button');
    toggle.textContent = task.completed ? 'Reopen' : 'Complete';
    toggle.onclick = async () => { await request('/api/tasks/' + task.id, {method: 'PATCH', body: JSON.stringify({completed: !task.completed})}); await load(); };
    const remove = document.createElement('button');
    remove.textContent = 'Delete';
    remove.onclick = async () => { await request('/api/tasks/' + task.id, {method: 'DELETE'}); await load(); };
    item.append(label, ' ', toggle, ' ', remove); tasks.append(item);
  }
}
document.querySelector('#new-task').onsubmit = async event => {
  event.preventDefault();
  const input = document.querySelector('#title');
  await request('/api/tasks', {method: 'POST', body: JSON.stringify({title: input.value})});
  input.value = ''; await load();
};
document.querySelector('#status').onchange = load;
load().catch(error => { message.textContent = error.message; });
</script>
```

Create `tests/test_task_ledger.py`:

```python
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from task_ledger.cli import create_task, list_tasks, make_server, update_task


class TaskLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temporary.name) / "tasks.db")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_crud_filter_and_persistence(self) -> None:
        first = create_task(self.database, "write docs")
        self.assertEqual([task["title"] for task in list_tasks(self.database, "open")], ["write docs"])
        update_task(self.database, int(first["id"]), {"title": "write guide", "completed": True})
        self.assertEqual([task["title"] for task in list_tasks(self.database, "completed")], ["write guide"])
        self.assertEqual(list_tasks(self.database), list_tasks(self.database))

    def test_cli_export_uses_selected_database(self) -> None:
        create_task(self.database, "export me")
        result = subprocess.run(
            [sys.executable, "-m", "task_ledger.cli", "--database", self.database, "export"],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(result.stdout)[0]["title"], "export me")

    def test_http_api_positive_and_negative_paths(self) -> None:
        server = make_server(self.database, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            health = json.load(urllib.request.urlopen(base + "/healthz"))
            self.assertEqual(health, {"status": "ok"})
            request = urllib.request.Request(
                base + "/api/tasks",
                data=json.dumps({"title": "from api"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            created = json.load(urllib.request.urlopen(request))
            open_tasks = json.load(urllib.request.urlopen(base + "/api/tasks?status=open"))
            self.assertEqual([task["id"] for task in open_tasks], [created["id"]])
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(base + "/api/tasks?status=invalid")
            self.assertEqual(raised.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
```

Finally create the authoritative product verifier `scripts/verify.sh` and make it executable:

```sh
cat > scripts/verify.sh <<'SH'
#!/bin/sh
set -eu
python -m unittest discover -s tests -v
SH
chmod +x scripts/verify.sh
```

At this point the verifier exists **before** the walkthrough asks you to run it. You can also start the application manually with:

```sh
python -m task_ledger.cli --database task-ledger.db serve --host 127.0.0.1 --port 8080
```

Then open `http://127.0.0.1:8080/` and exercise create, complete/reopen, delete, and filter behavior. The reference browser contract intentionally does not claim browser title editing. `PATCH /api/tasks/{id}` remains part of the independently supported API; adding a browser edit control is an ordinary consumer-owned extension that also requires matching browser contract and proof updates. The service and CLI remain independently callable.

### Add the real-browser viewport and keyboard proof

The Webapp evidence validator requires real positive and negative browser-level proof for the declared `viewports/base` and `input-capability/keyboard` targets. HTTP reachability and the unit/integration tests above do not satisfy that requirement.

Use a matching Chrome or Chrome for Testing binary and ChromeDriver. If they are not already installed, download the matching browser and driver archives from the official [Chrome for Testing availability dashboard](https://googlechromelabs.github.io/chrome-for-testing/) and extract them outside the product repository. Put `chromedriver` on `PATH`, or set `CHROMEWEBDRIVER` to its absolute path. When Chrome is not on the normal platform path, set `CHROME_BINARY` to the extracted browser executable.

**Check**

```sh
"${CHROME_BINARY:-google-chrome}" --version
"${CHROMEWEBDRIVER:-chromedriver}" --version
```

Download the reviewed standard-library WebDriver proof into the consumer-owned test directory. The full-SHA URL is immutable and the script has no Python package dependency:

```sh
python -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/TakashiSasaki/templates/ccf60eb3e137e664bd583a8403707d9f80c306f3/examples/onboarding/task-ledger/browser_proof.py', 'tests/test_task_ledger_browser.py')"
```

The proof starts Task Ledger with a temporary SQLite database and drives it through a real headless Chrome session. It covers:

- positive responsive behavior at narrow and landscape viewports;
- negative page-wide horizontal-overflow and zoom-lock checks;
- genuine 200% browser page-scale operability;
- positive keyboard create, complete, filter, and delete paths;
- negative empty-title keyboard submission; and
- an unknown-route browser negative path.

Add the browser proof to the authoritative verifier:

```sh
cat >> scripts/verify.sh <<'SH'
python tests/test_task_ledger_browser.py
SH
```

**Repository change**

Yes. The files above are ordinary consumer-owned implementation and verification material. They do not modify Composition-managed/generated paths.

**Next**

Run the product verifier you just created.

## 13. Define and run authoritative product verification

Composition does not choose the product test runner. Task Ledger now has one independently runnable consumer-owned command.

**Run**

```sh
./scripts/verify.sh
```

**Expected**

The consumer-owned unit/integration checks pass and the command exits successfully. The tests exercise SQLite persistence across independent connections, filtering/update behavior, CLI export, an independently reachable JSON API, health, and a negative invalid-filter case.

**Repository change**

The verifier does not rewrite Composition-owned material.

**What this means**

You now have product-behavior evidence that is separate from Composition's structural/contract validation. Before claiming browser edit behavior, either add the corresponding UI control and browser-facing proof or narrow the browser contract so it describes only the behavior actually exposed by the UI.

**Next**

Derive the exact evidence targets from the current contracts rather than inventing target IDs.

## 14. Generate the current evidence worklist

The Webapp scaffold includes a read-only deterministic generator.

**Run**

```sh
python scripts/scaffold_webapp_evidence.py > /tmp/webapp-evidence-worklist.json
```

**Expected**

A JSON worklist is written to the selected output file. `contracts/implementation-evidence.json` is unchanged.

**Repository change**

None from the generator itself. The redirected worklist above is outside the repository.

**What this means**

The target set comes from the actual current surface, route, state, and viewport contracts. If those contracts change, regenerate the worklist.

**Next**

For every current target, identify the implementation boundary, at least one positive proof, at least one negative proof, the authoritative command that produces those proofs, and a release gate that executes the referenced command.

Multiple records may reuse one command/gate when one suite genuinely proves multiple targets; do not manufacture one command per record.

## 15. Switch implementation evidence to product mode only after proof exists

The initial `contracts/implementation-evidence.json` is intentionally in `template` mode with no product implementation claim. Change it to `product` mode only after the implementation, `./scripts/verify.sh`, and referenced proof locations really exist.

The unit/integration portion of the Section 12 verifier is **not** browser-level proof by itself. The downloaded `tests/test_task_ledger_browser.py` adds real positive and negative `end-to-end-test` paths for the viewport and keyboard targets. If you skip that script or it does not run successfully in a real browser, keep implementation evidence in `template` mode. Do not relabel source inspection, HTTP reachability, or unit tests as browser proof.

A command and gate can look like:

```json
{
  "commands": [
    {
      "id": "verify-product",
      "command": "./scripts/verify.sh",
      "purpose": "Run Task Ledger product verification."
    }
  ],
  "releaseGates": [
    {
      "id": "product-verification",
      "purpose": "Require the authoritative product verification command.",
      "commandIds": ["verify-product"]
    }
  ]
}
```

Each record still needs its exact worklist target, verified implementation-boundary locator, verified positive/negative proof locators, expected results, and selected gate. Do not copy a sample target from this guide; the authoritative target set belongs to the consumer repository.

For the generated `viewports/base` and `input-capability/keyboard` records, use `tests/test_task_ledger_browser.py` as the positive and negative proof locator, `end-to-end-test` as the proof kind, and `verify-product` as the command ID. The expected results must describe the corresponding successful interaction and rejected/absent invalid behavior rather than merely saying that the file exists.

After every current target—including viewport and keyboard targets—has truthful proof of the required kind, run both verification layers.

**Run**

```sh
./scripts/verify.sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  validate
```

**Expected**

- the authoritative product verification command, including the referenced browser suite, passes; and
- Composition validation returns `status: "valid"` with implementation evidence executed rather than template-deferred.

If the real-browser script was omitted, skipped, or unable to start Chrome/ChromeDriver, this stronger product-mode result is not claimed; keep the evidence document in `template` mode.

**What this means**

Task Ledger now has both a product-behavior claim backed by consumer tests and a valid closed Composition contract/evidence relationship. This is the point at which “valid scaffold” and “implemented, product-tested application” have both been satisfied rather than confused.

## 16. Optionally adopt coding-agent Policy

Policy is a **separate authority**, not a Composition capability. Do not add a fictitious `capability.policy` to `composition.json`.

If coding agents will maintain Task Ledger, follow the Policy getting-started workflow after Composition has materialized its seeds and transferred those seeds to consumer ownership:

```text
Composition initial
  → consumer-owned seed/product implementation
  → explicit Policy adoption
  → Composition validation + Policy validation/check + product verification
```

Composition does not own `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`. Use the published [Policy getting-started guide](https://templates.moukaeritai.work/policy/getting-started/) for the Policy-owned adoption commands rather than copying those semantics into this Composition tutorial.

## 17. Make ordinary product changes normally

Adding a Task Ledger feature, changing SQLite queries, editing consumer-owned seed contracts, or adding product tests is ordinary repository work. It does not require a Composition `update` merely because the product changed.

After a product change:

1. update consumer-owned contracts/evidence truthfully;
2. run `./scripts/verify.sh`;
3. run Composition `validate`;
4. run Policy validation/check as well if Policy is adopted.

Use Composition lifecycle operations only when the Composition source/intent itself changes.

## 18. Update or upgrade Composition later

When the installed runner selects a newer reviewed Composition revision, inspect first.

For unchanged intent and no compatibility-boundary change:

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  inspect
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --mode update
```

Review the read-only plan. If acceptable:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --mode update
```

Consumer-owned seed changes are preserved; clean managed/generated material may be replaced or removed according to the reviewed plan.

If the plan reports `COMPONENT_VERSION_UPGRADE_REQUIRED`, or if Task Ledger intentionally changes recipe/components/parameters, make that boundary explicit:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --mode upgrade --config /absolute/path/to/task-ledger/composition.json

python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --mode upgrade --config /absolute/path/to/task-ledger/composition.json
```

Then rerun product verification and Composition validation. Do not edit lock metadata to turn an update/upgrade conflict into apparent success.

## Completion checklist

At the **first-use scaffold milestone**, you have succeeded when:

- Task Ledger is a separate product repository;
- the Composition skill is installed outside it;
- `composition.json` states the intended Webapp/capability selection;
- `inspect → plan → review → apply → validate` was followed in order;
- the plan was understood as read-only before mutation;
- Composition validation is valid; and
- you can identify concrete files that are editable seeds, Composition-owned managed/generated material, and ordinary product code.

The **implemented-product milestone** is stronger. It additionally requires:

- consumer-owned contracts describe the real product rather than template assumptions;
- product source and tests exist;
- the authoritative product verification command passes;
- implementation evidence is in `product` mode with complete current-target coverage and real positive/negative proofs, including browser-level proof for browser-sensitive targets;
- Composition validation passes with implementation evidence executed rather than template-deferred; and
- optional Policy state is independently valid if Policy was adopted.

If you reached the first milestone, you no longer need to infer what to do next: edit the consumer-owned Task Ledger contracts, add ordinary product source/tests, and proceed through Sections 11–15. Architecture, exact ownership rules, managed recovery, and immutable-source details remain available in [Using Composition](../consumer-guide.md) and the [Composer reference](../reference/composer.md) when you need them.