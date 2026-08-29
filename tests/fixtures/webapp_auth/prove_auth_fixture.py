from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True

import auth_app
from browser_probe import _open_webdriver_session, run_browser_contract_probe

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
ui_states = json.loads(
    (ROOT / "contracts/ui-states.json").read_text(encoding="utf-8")
)["states"]
states_by_id = {state["id"]: state for state in ui_states}
for route_id, surface_id, required_role in (
    ("application-home", "application", "application-user"),
    ("admin", "admin", "admin"),
):
    route = routes[route_id]
    surface = surfaces[surface_id]
    assert route["authentication"] == "required"
    assert route["accessFailures"] == {
        "unauthenticated": {
            "behavior": "render-state",
            "stateId": "unauthorized",
        },
        "forbidden": {
            "behavior": "render-state",
            "stateId": "forbidden",
        },
    }
    assert {
        "loading",
        "populated",
        "recoverable-error",
        "unauthorized",
        "forbidden",
    } <= set(route["states"])
    assert surface["authorization"] == {"mode": "role", "roles": [required_role]}

for route in routes.values():
    assert route["accessibility"]["documentTitleRequired"] is True
    assert route["accessibility"]["focusTarget"] == "main-heading"

viewports = json.loads(
    (ROOT / "contracts/viewports.json").read_text(encoding="utf-8")
)
browser_identity = json.loads(
    (ROOT / "contracts/browser-identity.json").read_text(encoding="utf-8")
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
assert browser_identity["favicon"] == {
    "relation": "icon",
    "href": "favicon.svg",
    "mediaType": "image/svg+xml",
    "sizes": ["any"],
    "fallbacks": [],
}

client_source = (ROOT / "product/client.html").read_text(encoding="utf-8")
assert '<title>Composition Webapp auth fixture</title>' in client_source
assert '<link rel="icon" href="favicon.svg" type="image/svg+xml" sizes="any">' in client_source
assert 'id="main-heading"' in client_source
assert 'id="error-summary"' in client_source
assert 'id="error-heading"' in client_source
assert 'name="viewport"' in client_source
assert "width=device-width" in client_source
assert "user-scalable=no" not in client_source
assert "@media (min-width: 768px)" in client_source
assert "@media (min-width: 1280px)" in client_source
assert "overflow-x: auto" in client_source
assert '<button type="button"' in client_source
assert "orientation:" not in client_source
assert 'document.getElementById(focusStrategy).focus()' in client_source
assert 'button.dataset.recoveryAction = action' in client_source

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
) -> str:
    status, body = request(path, user=user, roles=roles)
    assert status == expected_status, (path, status, body)
    assert f'data-surface="{expected_surface}"' in body, body
    assert f'data-state="{expected_state}"' in body, body
    assert '<meta name="viewport"' in body, body
    assert '<link rel="icon" href="favicon.svg" type="image/svg+xml" sizes="any">' in body, body
    assert '<button type="button"' in body, body

    state = states_by_id[expected_state]
    expected_aria_live = (
        "off" if state["announcement"] == "none" else state["announcement"]
    )
    assert f'data-focus-strategy="{state["focusStrategy"]}"' in body, body
    assert f'aria-live="{expected_aria_live}"' in body, body
    recovery_actions = ",".join(state["recoveryActions"])
    assert f'data-recovery-actions="{recovery_actions}"' in body, body
    return expected_state


observed_states: set[str] = set()
try:
    run_browser_contract_probe(base + "/", viewports)
    with _open_webdriver_session() as browser:
        browser.navigate(base + "/")
        identity = browser.execute(
            """
            const links = Array.from(document.querySelectorAll('link[rel]')).map((link) => ({
              relTokens: link.getAttribute('rel').trim().toLowerCase().split(/\s+/),
              rawHref: link.getAttribute('href'),
              resolvedHref: link.href,
              mediaType: link.getAttribute('type') || '',
              sizes: link.sizes ? Array.from(link.sizes) : [],
            }));
            return {
              shortcutCount: links.filter((item) => item.relTokens.includes('shortcut')).length,
              iconLinks: links.filter((item) => item.relTokens.includes('icon')),
            };
            """
        )
        assert isinstance(identity, dict), identity
        assert identity["shortcutCount"] == 0, identity
        primary = next(
            item
            for item in identity["iconLinks"]
            if item["rawHref"] == browser_identity["favicon"]["href"]
        )
        assert primary["relTokens"] == ["icon"], primary
        assert primary["mediaType"] == browser_identity["favicon"]["mediaType"], primary
        assert primary["sizes"] == browser_identity["favicon"]["sizes"], primary
        browser.navigate(primary["resolvedHref"])
        favicon_asset = browser.execute(
            """
            return {
              contentType: document.contentType,
              rootName: document.documentElement ? document.documentElement.localName : null,
            };
            """
        )
        assert favicon_asset == {
            "contentType": "image/svg+xml",
            "rootName": "svg",
        }, favicon_asset

        for route in routes.values():
            focus_target = route["accessibility"]["focusTarget"]
            browser.navigate(base + route["path"])
            focus_result = browser.execute(
                """
                const element = document.getElementById(arguments[0]);
                if (!element) return {exists: false};
                let visible = true;
                for (let current = element; current; current = current.parentElement) {
                  const style = getComputedStyle(current);
                  if (style.display === 'none' || style.visibility === 'hidden'
                      || Number.parseFloat(style.opacity || '1') <= 0) visible = false;
                }
                const rect = element.getBoundingClientRect();
                return {
                  exists: true,
                  visible: visible && rect.width > 0 && rect.height > 0
                    && rect.right > 0 && rect.bottom > 0
                    && rect.left < window.innerWidth && rect.top < window.innerHeight,
                  explicitlyFocusable: element.hasAttribute('tabindex'),
                  focused: document.activeElement === element,
                };
                """,
                focus_target,
            )
            assert focus_result == {
                "exists": True,
                "visible": True,
                "explicitlyFocusable": True,
                "focused": True,
            }, (route["id"], focus_result)
    observed_states.add(assert_view(200, "public", "populated", "/"))
    observed_states.add(assert_view(200, "status", "populated", "/status"))
    observed_states.add(assert_view(401, "application", "unauthorized", "/app"))
    observed_states.add(
        assert_view(
            200,
            "application",
            "populated",
            "/app",
            user="alice",
            roles=("application-user",),
        )
    )
    observed_states.add(
        assert_view(
            403,
            "application",
            "forbidden",
            "/app",
            user="alice",
            roles=("admin",),
        )
    )
    observed_states.add(assert_view(401, "admin", "unauthorized", "/admin"))
    observed_states.add(
        assert_view(
            403,
            "admin",
            "forbidden",
            "/admin",
            user="alice",
            roles=("application-user",),
        )
    )
    observed_states.add(
        assert_view(
            200,
            "admin",
            "populated",
            "/admin",
            user="alice",
            roles=("admin",),
        )
    )
    for state, status in (
        ("loading", 200),
        ("empty", 200),
        ("partial", 206),
        ("recoverable-error", 503),
        ("retrying", 202),
        ("offline", 503),
    ):
        observed_states.add(
            assert_view(
                status,
                "application",
                state,
                f"/app?state={state}",
                user="alice",
                roles=("application-user",),
            )
        )
    observed_states.add(assert_view(500, "public", "fatal-error", "/__fatal"))
    observed_states.add(assert_view(404, "public", "not-found", "/missing"))
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    assert not thread.is_alive()

assert observed_states == set(states_by_id)
print("Browser identity proof: standard favicon linkage and primary asset retrieval passed")
print(
    "Webapp auth product proof: route access, complete UI-state, real-browser viewport/input, and accessibility behavior passed"
)
