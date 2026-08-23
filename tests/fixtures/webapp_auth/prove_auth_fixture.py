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

viewports = json.loads(
    (ROOT / "contracts/viewports.json").read_text(encoding="utf-8")
)
assert [
    (viewport["id"], viewport["minWidthPx"])
    for viewport in viewports["viewports"]
] == [("compact", 0), ("regular", 768), ("wide", 1280)]
assert set(viewports["inputCapabilities"]) == {"touch", "pointer", "keyboard"}
assert viewports["constraints"] == {
    "zoomSupported": True,
    "horizontalScrolling": "content-specific",
    "orientationIndependent": True,
}

client_source = (ROOT / "product/client.html").read_text(encoding="utf-8")
assert 'name="viewport"' in client_source
assert "width=device-width" in client_source
assert "user-scalable=no" not in client_source
assert "@media (min-width: 768px)" in client_source
assert "@media (min-width: 1280px)" in client_source
assert "overflow-x: auto" in client_source
assert '<button type="button"' in client_source
assert "orientation:" not in client_source

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
            return response.status, response.read().decode("utf-8")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def assert_view(
    expected_status: int,
    expected_surface: str,
    expected_state: str,
    path: str,
    *,
    user: str | None = None,
    roles: tuple[str, ...] = (),
) -> None:
    status, body = request(path, user=user, roles=roles)
    assert status == expected_status, (path, status, body)
    assert f'data-surface="{expected_surface}"' in body, body
    assert f'data-state="{expected_state}"' in body, body
    assert '<meta name="viewport"' in body, body
    assert '<button type="button"' in body, body


try:
    assert_view(200, "public", "populated", "/")
    assert_view(200, "status", "populated", "/status")
    assert_view(401, "application", "unauthorized", "/app")
    assert_view(
        200,
        "application",
        "populated",
        "/app",
        user="alice",
        roles=("application-user",),
    )
    assert_view(
        403,
        "application",
        "forbidden",
        "/app",
        user="alice",
        roles=("admin",),
    )
    assert_view(401, "admin", "unauthorized", "/admin")
    assert_view(
        403,
        "admin",
        "forbidden",
        "/admin",
        user="alice",
        roles=("application-user",),
    )
    assert_view(
        200,
        "admin",
        "populated",
        "/admin",
        user="alice",
        roles=("admin",),
    )
    assert_view(
        200,
        "application",
        "loading",
        "/app?state=loading",
        user="alice",
        roles=("application-user",),
    )
    assert_view(
        503,
        "application",
        "recoverable-error",
        "/app?state=recoverable-error",
        user="alice",
        roles=("application-user",),
    )
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    assert not thread.is_alive()

print("Webapp auth product proof: route access, UI-state, and viewport behavior passed")
