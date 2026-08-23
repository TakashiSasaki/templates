from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import auth_app

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    ("contracts", (sys.executable, "scripts/validate_contracts.py")),
    (
        "contract evolution",
        (
            sys.executable,
            ".template-composition/validators/validate_contract_evolution.py",
            ".",
        ),
    ),
    (
        "implementation evidence",
        (
            sys.executable,
            ".template-composition/validators/validate_implementation_evidence.py",
            ".",
        ),
    ),
    (
        "release execution",
        (
            sys.executable,
            ".template-composition/validators/validate_release_execution.py",
            ".",
        ),
    ),
    (
        "Webapp evidence coverage",
        (sys.executable, "scripts/validate_webapp_evidence.py"),
    ),
)

for label, command in CHECKS:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"{label} failed", file=sys.stderr)
        print(result.stdout, file=sys.stderr, end="")
        print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)

routes = {
    route["id"]: route
    for route in json.loads(
        (ROOT / "contracts/routes.json").read_text(encoding="utf-8")
    )["routes"]
}
surfaces = {
    surface["id"]: surface
    for surface in json.loads(
        (ROOT / "contracts/surfaces.json").read_text(encoding="utf-8")
    )["surfaces"]
}
for route_id, surface_id, required_role in (
    ("application-home", "application", "application-user"),
    ("admin", "admin", "admin"),
):
    route = routes[route_id]
    surface = surfaces[surface_id]
    assert route["authentication"] == "required"
    assert route["accessFailures"] == {
        "unauthenticated": "render-state",
        "forbidden": "render-state",
    }
    assert {
        "loading",
        "populated",
        "recoverable-error",
        "unauthorized",
        "forbidden",
    } <= set(route["states"])
    assert surface["authorization"] == {"mode": "role", "roles": [required_role]}

server = auth_app.make_server()
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
base = f"http://127.0.0.1:{server.server_address[1]}"


def request(
    path: str,
    *,
    user: str | None = None,
    roles: tuple[str, ...] = (),
) -> tuple[int, str]:
    headers: dict[str, str] = {}
    if user is not None:
        headers["X-User"] = user
    if roles:
        headers["X-Roles"] = ",".join(roles)
    try:
        with urlopen(Request(base + path, headers=headers), timeout=5) as response:
            return response.status, response.read().decode("utf-8").strip()
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8").strip()


try:
    assert request("/") == (200, "public:populated")
    assert request("/app") == (401, "unauthorized")
    assert request(
        "/app", user="alice", roles=("application-user",)
    ) == (200, "app:populated")
    assert request("/app", user="alice", roles=("admin",)) == (403, "forbidden")
    assert request("/admin") == (401, "unauthorized")
    assert request(
        "/admin", user="alice", roles=("application-user",)
    ) == (403, "forbidden")
    assert request("/admin", user="alice", roles=("admin",)) == (
        200,
        "admin:populated",
    )
    assert request(
        "/app?state=loading", user="alice", roles=("application-user",)
    ) == (200, "app:loading")
    assert request(
        "/app?state=recoverable-error",
        user="alice",
        roles=("application-user",),
    ) == (503, "recoverable-error")
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)

print("Webapp auth product proof: route access and UI-state behavior passed")
