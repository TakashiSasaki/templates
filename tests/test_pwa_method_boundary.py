from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PwaMethodBoundaryTests(unittest.TestCase):
    def test_service_worker_ignores_non_get_requests_before_document_dispatch(self) -> None:
        worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        method_guard = worker.index('if (event.request.method !== "GET")')
        document_dispatch = worker.index("if (isDocumentRequest(event.request, url))")
        self.assertLess(method_guard, document_dispatch)
        guard_block = worker[method_guard:document_dispatch]
        self.assertIn("return;", guard_block)


if __name__ == "__main__":
    unittest.main()
