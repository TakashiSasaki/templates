from __future__ import annotations

from pathlib import Path


PATH = Path("examples/onboarding/task-ledger/browser_proof.py")
text = PATH.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match, found {count}: {old[:80]!r}")
    text = text.replace(old, new)


replace_once(
    """class BrowserProofError(RuntimeError):
    pass


def driver_path() -> str:
""",
    """class BrowserProofError(RuntimeError):
    pass


class _WebDriverTransportError(BrowserProofError):
    pass


class _WebDriverBootstrapError(BrowserProofError):
    pass


def driver_path() -> str:
""",
)

replace_once(
    """        self.session_id: str | None = None
        try:
            self.wait_ready()
            self.start_session()
        except BaseException:
            self.close()
            raise
""",
    """        self.session_id: str | None = None
        try:
            self.wait_ready()
            self.start_session()
        except _WebDriverTransportError as exc:
            self.close()
            raise _WebDriverBootstrapError(
                f"ChromeDriver session bootstrap transport failed: {exc}"
            ) from exc
        except BaseException:
            self.close()
            raise
""",
)

replace_once(
    """        except URLError as exc:
            raise BrowserProofError(f"WebDriver {method} {path}: {exc}") from exc
""",
    """        except (URLError, TimeoutError) as exc:
            raise _WebDriverTransportError(
                f"WebDriver {method} {path} transport failed: {exc}"
            ) from exc
""",
)

replace_once(
    """    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def require(condition: bool, message: str) -> None:
""",
    """    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def open_browser_session() -> BrowserSession:
    last_error: _WebDriverBootstrapError | None = None
    for attempt in range(2):
        try:
            return BrowserSession()
        except _WebDriverBootstrapError as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(0.1)
    assert last_error is not None
    raise BrowserProofError(
        "ChromeDriver session bootstrap failed after 2 attempts"
    ) from last_error


def require(condition: bool, message: str) -> None:
""",
)

replace_once(
    """def run_browser_proof(base_url: str) -> None:
    with BrowserSession() as browser:
""",
    """def run_browser_proof(base_url: str) -> None:
    with open_browser_session() as browser:
""",
)

PATH.write_text(text, encoding="utf-8")
