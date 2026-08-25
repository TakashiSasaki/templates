# Webapp product walkthrough

> **参考訳（非正本）:** この文書は英語版 `docs/guides/webapp-product-walkthrough.md` の日本語参考訳です。正本は英語版であり、内容または解釈に相違がある場合は英語版が優先されます。

これは Composition で Web application を作る canonical first-use walkthrough です。Composition architecture を先に読む必要はありません。上から順に進めてください。

例は **Task Ledger** です。browser UI、SQLite 永続化、独立 HTTP JSON API、`list` / `export` CLI を持つ小さな product を作ります。Python / SQLite は Task Ledger の product decision であり、Composition の推奨 technology ではありません。

## 0. この walkthrough で何を作るか

`TakashiSasaki/templates` 自体を application repository にするのではなく、**別の `task-ledger` product repository** を作ります。

```text
TakashiSasaki/templates
        |
        | Composition tooling と contracts を提供
        v
あなたの別 task-ledger product repository
```

最初の milestone は次です。

```text
separate repository
  ↓
Composition install
  ↓
composition.json
  ↓
inspect → plan → review → apply → validate
  ↓
valid Composition scaffold
  ↓
明確な editing boundary
```

この `VALID` は product implementation / product test の完了を意味しません。後半で consumer-owned implementation、product verification、implementation evidence、optional Policy、update/upgrade まで進みます。

canonical command は path inference を避けるため absolute `--repository` / `--config` を使います。

## 1. 別 product repository を作る

**Run**

```sh
mkdir /absolute/path/to/task-ledger
cd /absolute/path/to/task-ledger
git init
```

**Expected:** 独立した Git repository ができ、`.template-composition/lock.json` はまだありません。

**Repository change:** repository 自体を作成します。Composition material はまだありません。

**Next:** prerequisites を確認します。

## 2. Prerequisites を確認する

supported prerequisites は Git と CPython 3.11–3.14 です。

```sh
git --version
python --version
```

sandbox / CI の user cache が writable でなければ、`COMPOSITION_RUNTIME_CACHE` と `COMPOSITION_VALIDATION_CACHE` を product repository 外の writable directory に設定します。

**Repository change:** なし。

**Next:** Composition を install します。

## 3. Composition を install する

product repository 外へ reviewed immutable installer で install します。

```sh
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/9c1c093fca1e7e47a9974150e7739665ec570f6e/scripts/install_composition_skill.py', timeout=30).read())" /absolute/path/to/agent-skills/composition
```

**Expected:** `/absolute/path/to/agent-skills/composition/scripts/run.py` が存在します。

**Repository change:** Task Ledger にはなし。

full SHA は immutable-source model のためです。詳細は [Using Composition](../consumer-guide.md#immutable-source-runtime-selection-and-cache-reuse) を参照してください。

## 4. `composition.json` を作る

Task Ledger は Webapp baseline に加えて runtime、独立 service、caller-visible CLI を選びます。

`/absolute/path/to/task-ledger/composition.json`:

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

同じ machine-checked example は `examples/onboarding/task-ledger/composition.json` にあります。

**Repository change:** `composition.json` は consumer-owned intent として追加されます。scaffold はまだありません。

## 5. Repository を inspect する

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  inspect
```

**Expected:** new directory なら `state: "unmanaged"`。directory 自体がなければ `absent` も正常です。

**Repository change:** なし。`inspect` は read-only です。

`managed-valid` / `managed-invalid` / `managed-interrupted` なら fresh initial として進めず、[Using Composition](../consumer-guide.md#check-whether-a-repository-is-managed) の state-specific workflow を使います。

## 6. Initial materialization を plan する

absolute `--config` を使います。relative `--config` は `--repository` ではなく **process current working directory** 基準です。

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --config /absolute/path/to/task-ledger/composition.json
```

**Expected:** `operation: "initial"`、resolved components、`actions`、`conflicts`、`lock_preview`。fresh repository なら通常 `conflicts` は empty です。

**Repository change:** なし。plan は read-only です。

## 7. Plan を review する

`target`、intent、全 `actions`、`conflicts` を確認します。conflict がある場合は apply せず、既存 destination が異なる理由を解決してください。metadata の rename/delete で conflict を隠してはいけません。

**Repository change:** なし。

## 8. Scaffold を apply する

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --config /absolute/path/to/task-ledger/composition.json
```

**Expected:** `status: "applied"`、`operation: "initial"`、created/adopted destinations、`lock: ".template-composition/lock.json"`。

**Repository change:** あり。これが最初の materialization step です。

## 9. Scaffold を validate する

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  validate
```

**Expected:** public JSON result が `status: "valid"`。initial implementation evidence は `template` mode なので product claim は deferred です。

> **Composition validation: VALID** は Composition state / template contracts が valid という意味で、Task Ledger が実装済み・product-tested という意味ではありません。

## 10. Generated tree と editing boundary を確認する

`.template-composition/lock.json` を読みます。lock 自体は編集しません。

| File | Ownership | Action |
| --- | --- | --- |
| `README.md`, `TEMPLATE.md`, `RUNTIME.md`, `CLI_INTERFACE.md`, `SERVICE_INTERFACE.md` | `seed` | **編集する。** consumer ownership に移っています。 |
| Webapp contract JSON | `seed` | **編集する。** product の実態に合わせる。 |
| `contracts/implementation-evidence.json` | `seed` | **real proof ができてから編集する。** |
| `contracts/manifest.json` | `generated` | **hand-edit しない。** |
| `schemas/*.schema.json` | `managed` | **hand-edit しない。** |
| `.github/workflows/validate-webapp.yml` | `managed` | **hand-edit しない。** |
| scaffold validators / `.template-composition/*` managed material | `managed` | **hand-edit しない。** |
| `.template-composition/lock.json` | Composer state | **hand-edit しない。** |
| `task_ledger/cli.py`, `tests/test_task_ledger.py` などの新規 path | ordinary consumer content | **通常どおり作成・編集する。** |

`seed` は initial materialization 後に consumer-owned、`managed` / `generated` は Composition-owned、lock にない path は原則 ordinary consumer content です。

## 11. Template assumption を実際の product contract に置き換える

Task Ledger が本当に実装する contract だけを残します。

Browser: `primary` surface、`/` の home route、実際に表示する state、tested viewport/input behavior を記述します。

`RUNTIME.md` の例:

```text
Implementation ecosystem: CPython 3.11+
Persistence: SQLite
Server command: python -m task_ledger.cli --database task-ledger.db serve --host 127.0.0.1 --port 8080
Distribution: source execution for this example
```

`SERVICE_INTERFACE.md` の小さな API:

```text
GET    /api/tasks?status=all|open|completed
GET    /api/tasks/{id}
POST   /api/tasks
PATCH  /api/tasks/{id}
DELETE /api/tasks/{id}
GET    /healthz
```

`CLI_INTERFACE.md`:

```sh
python -m task_ledger.cli --database task-ledger.db list --status all
python -m task_ledger.cli --database task-ledger.db export
```

## 12. Minimal consumer-owned implementation と tests を作る

ここからは hypothetical tree ではなく、Section 13 で実際に実行できる product code / tests / verifier を作ります。以下はすべて lock に存在しない ordinary consumer content です。

```sh
mkdir -p task_ledger/static tests scripts
touch task_ledger/__init__.py
```

`task_ledger/cli.py` を作成します。

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

`task_ledger/static/index.html`:

```html
<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Task Ledger</title>
<h1>Task Ledger</h1>
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

`tests/test_task_ledger.py`:

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

Section 13 の authoritative verifier を**実行前に作成**します。

```sh
cat > scripts/verify.sh <<'SH'
#!/bin/sh
set -eu
python -m unittest discover -s tests -v
SH
chmod +x scripts/verify.sh
```

manual start:

```sh
python -m task_ledger.cli --database task-ledger.db serve --host 127.0.0.1 --port 8080
```

`http://127.0.0.1:8080/` で create、complete/reopen、delete、filter を確認できます。title edit は `PATCH /api/tasks/{id}` に実装されていますが minimal browser UI には edit control がありません。browser-edit evidence を claim する前に edit control と proof を追加するか、browser contract を実際の UI behavior に狭めます。

**Repository change:** 上記は ordinary consumer-owned implementation / verification material です。

## 13. Authoritative product verification を定義して実行する

Composition は product test runner を選びません。ここでは Section 12 で作成した consumer-owned verifier を実行します。

```sh
./scripts/verify.sh
```

**Expected:** unit/integration checks が pass し exit 0。SQLite persistence、filter/update、CLI export、independent JSON API、health、negative invalid-filter case を検査します。

**What this means:** Composition structural validation とは別の product-behavior evidence が存在します。browser edit を claim するなら、先に UI control/proof を追加するか contract を実態へ合わせます。

## 14. 現在の evidence worklist を生成する

```sh
python scripts/scaffold_webapp_evidence.py > /tmp/webapp-evidence-worklist.json
```

これは read-only generator で、`contracts/implementation-evidence.json` を変更しません。actual current contracts から target set を導出します。

各 target について implementation boundary、positive proof、negative proof、authoritative command、release gate を特定します。同じ suite が複数 target を本当に証明するなら command/gate の再利用は可能です。

## 15. Proof が存在してから implementation evidence を product mode にする

initial `contracts/implementation-evidence.json` は `template` mode です。implementation、`./scripts/verify.sh`、proof location が実在してから `product` mode にします。

command/gate 例:

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

各 record は actual worklist target、implementation-boundary locator、positive/negative proof locators、expected results、selected gate を持つ必要があります。

```sh
./scripts/verify.sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  validate
```

product verification が pass し、Composition validation が `status: "valid"`、implementation evidence が template-deferred ではなく executed されることを確認します。

## 16. 必要なら coding-agent Policy を adopt する

Policy は **separate authority** であり Composition capability ではありません。`capability.policy` のような fictitious component を追加しません。

coding agents が Task Ledger を保守する場合は、Composition initial 後に [Policy getting-started guide](https://templates.moukaeritai.work/policy/getting-started/) を使います。Composition は `.agent-policy.yml`、`.agent-policy.lock`、`.agent-policy/**` を所有しません。

## 17. 通常の product change は通常どおり行う

product feature、SQLite query、consumer-owned seed contract、product tests の変更は ordinary repository work です。product が変わっただけでは Composition `update` は不要です。

変更後は contracts/evidence を truthful にし、`./scripts/verify.sh`、Composition `validate`、必要なら Policy validation/check を実行します。

## 18. 後で Composition を update / upgrade する

unchanged intent で compatible な新 revision へ進む場合:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  inspect
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --mode update
```

read-only plan を review 後:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --mode update
```

`COMPONENT_VERSION_UPGRADE_REQUIRED` または intentional intent change なら explicit upgrade:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --mode upgrade --config /absolute/path/to/task-ledger/composition.json
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --mode upgrade --config /absolute/path/to/task-ledger/composition.json
```

lock metadata を hand-edit して conflict を成功に見せてはいけません。

## Completion checklist

**First-use scaffold milestone:** separate product repository、Composition install、`composition.json`、正しい `inspect → plan → review → apply → validate`、read-only plan の理解、valid scaffold、editing boundary の理解。

**Implemented-product milestone:** truthful consumer contracts、product source/tests、passing product verifier、complete product-mode implementation evidence、executed implementation-evidence を含む valid Composition validation、必要なら独立した valid Policy state。

first milestone 後の next action は明確です。consumer-owned contracts を product の実態へ合わせ、Section 12 で ordinary source/tests を作り、Sections 13–15 へ進みます。詳細 reference は [Using Composition](../consumer-guide.md) と [Composer reference](../reference/composer.md) を使用してください。