from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_pwa_slow_convergence  # noqa: E402


class PwaSlowConvergenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.worker = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.client = (ROOT / "assets/javascripts/pwa.js").read_text(encoding="utf-8")
        self.checker = (ROOT / "scripts/check_pwa_slow_convergence.py").read_text(
            encoding="utf-8"
        )
        self.workflow = (ROOT / ".github/workflows/mobile-visual-regression.yml").read_text(
            encoding="utf-8"
        )

    def test_soft_timeout_uses_existing_synchronous_event_lifetime(self) -> None:
        self.assertIn("const DOCUMENT_SOFT_TIMEOUT_MS = 1500", self.worker)
        self.assertIn("const networkOutcomePromise = startDocumentNetworkRequest(event.request)", self.worker)
        self.assertIn("softTimeoutSignal()", self.worker)
        self.assertIn("registerBackgroundTask(\n    convergeAfterChecking(", self.worker)
        self.assertIn("event.waitUntil(lifetimePromise)", self.worker)
        self.assertIn("event.respondWith(responsePromise)", self.worker)
        self.assertNotIn("event.waitUntil(\n    convergeAfterChecking", self.worker)
        self.assertNotIn("AbortController", self.worker)
        self.assertNotIn("controller.abort", self.worker)

    def test_cache_miss_after_soft_timeout_waits_for_network(self) -> None:
        self.assertIn("if (!afterTimeout.response)", self.worker)
        self.assertIn("await networkOutcomePromise", self.worker)
        self.assertIn('evidence["cache_miss_waited_for_network"] = True', self.checker)

    def test_instant_checking_requires_generation_bound_acknowledgement(self) -> None:
        self.assertIn('"checking",\n      generation,\n      true', self.worker)
        self.assertIn('type: "templates:freshness-state-applied"', self.client)
        self.assertIn("requestGeneration: data.requestGeneration", self.client)
        self.assertIn("workerInstanceId: data.workerInstanceId", self.client)
        self.assertIn('data-freshness-state="${state}"', self.worker)
        self.assertIn('headers.set("X-Templates-Freshness", state)', self.worker)

    def test_worker_instance_scopes_generation_ordering(self) -> None:
        self.assertIn("const WORKER_INSTANCE_ID = self.crypto.randomUUID()", self.worker)
        self.assertIn("workerInstanceId: WORKER_INSTANCE_ID", self.worker)
        self.assertIn("data.workerInstanceId === WORKER_INSTANCE_ID", self.worker)
        self.assertIn("let workerInstanceId = null", self.client)
        self.assertIn("function resetWorkerOrdering(", self.client)
        self.assertIn("function adoptWorkerInstance(", self.client)
        self.assertIn("resetWorkerOrdering(nextWorkerInstanceId)", self.client)
        self.assertIn("if (!adoptWorkerInstance(data.workerInstanceId))", self.client)
        self.assertIn("resetWorkerOrdering();", self.client)
        self.assertIn('evidence["worker_restart_generation_reset"] = True', self.checker)

    def test_full_navigation_never_requires_ui_acknowledgement(self) -> None:
        fallback_start = self.worker.index("async function fallbackForCompletedFailure")
        fallback_end = self.worker.index("async function handleCompletedDocumentNetwork", fallback_start)
        fallback = self.worker[fallback_start:fallback_end]
        navigation_start = fallback.index('if (event.request.mode === "navigate")')
        acknowledgement_start = fallback.index("const acknowledged = await publishFreshnessState(")
        navigation_branch = fallback[navigation_start:acknowledgement_start]
        self.assertIn(
            'rememberFreshnessState(event, "cached-unverified", generation)',
            navigation_branch,
        )
        self.assertIn("return cached;", navigation_branch)
        self.assertNotIn("publishFreshnessState(", navigation_branch)

        document_start = self.worker.index("async function fetchDocumentNetworkFirst")
        document_end = self.worker.index("function respondWithDocumentNetworkFirst", document_start)
        document_flow = self.worker[document_start:document_end]
        checking_navigation = document_flow.index('if (event.request.mode === "navigate")')
        checking_else = document_flow.index("} else {", checking_navigation)
        self.assertIn(
            'rememberFreshnessState(event, "checking", generation)',
            document_flow[checking_navigation:checking_else],
        )
        self.assertNotIn(
            "publishFreshnessState(",
            document_flow[checking_navigation:checking_else],
        )
        self.assertIn('evidence["full_navigation_without_preexisting_client_ack"] = True', self.checker)

    def test_background_completion_converges_by_robust_revision_extraction(self) -> None:
        self.assertIn("async function convergeAfterChecking(", self.worker)
        self.assertIn("function extractMetaAttributes(tag)", self.worker)
        self.assertIn("source.match(/<meta\\b[^>]*>/gi)", self.worker)
        self.assertIn("previousRevision === nextRevision", self.worker)
        self.assertIn('"verified-current"', self.worker)
        self.assertIn('"update-available"', self.worker)
        self.assertIn('"cached-unverified"', self.worker)
        self.assertIn('evidence["reordered_meta_verified_current"] = True', self.checker)
        self.assertIn('evidence["missing_revision_update_available"] = True', self.checker)
        self.assertIn('evidence["non_html_update_available"] = True', self.checker)

    def test_background_state_delivery_targets_current_document(self) -> None:
        self.assertIn('self.clients.matchAll({ type: "window" })', self.worker)
        self.assertIn("documentStateKey(client.url) === targetKey", self.worker)
        self.assertIn("documentStateKey(client.url) !== targetKey", self.worker)
        self.assertIn("if (requireAcknowledgement) {\n      return false;", self.worker)
        self.assertIn(
            'normalizedUrl !== normalizedDocumentUrl(window.location.href)',
            self.client,
        )
        self.assertIn("requestCurrentFreshnessState();", self.client)
        self.assertIn('evidence["previous_document_convergence_ignored"] = True', self.checker)

    def test_newer_network_commit_retires_older_convergence(self) -> None:
        self.assertIn("if (!documentRemembered) {\n    return false;", self.worker)
        self.assertIn(
            "lastFreshnessGeneration = Math.max(\n        lastFreshnessGeneration,\n        pending.generation",
            self.client,
        )
        self.assertIn('evidence["newer_commit_retired_old_convergence"] = True', self.checker)

    def test_remembered_states_are_bounded_and_generation_ordered(self) -> None:
        self.assertIn("const MAX_REMEMBERED_FRESHNESS_STATES = 64", self.worker)
        self.assertIn("while (map.size > MAX_REMEMBERED_FRESHNESS_STATES)", self.worker)
        self.assertIn("previous.generation > value.generation", self.worker)
        self.assertIn("clientFreshnessStates", self.worker)
        self.assertIn("documentFreshnessStates", self.worker)

    def test_client_supports_all_active_states_without_regressing_commit_boundary(self) -> None:
        for state in ("checking", "cached-unverified", "update-available", "verified-current"):
            with self.subTest(state=state):
                self.assertIn(f'"{state}"', self.client)
        self.assertIn('reload.textContent = "Reload"', self.client)
        self.assertIn("window.location.reload()", self.client)
        self.assertIn('type: "templates:get-current-freshness-state"', self.client)
        self.assertIn("lastFreshnessGeneration", self.client)
        self.assertIn("pendingDocumentCommit", self.client)
        self.assertIn('pending.representation === "cached"', self.client)
        self.assertIn("document.body || document.documentElement", self.client)

    def test_chromium_checker_covers_convergence_edge_cases(self) -> None:
        self.assertIn('evidence["instant_checking"] = True', self.checker)
        self.assertIn('evidence["instant_update_available"] = True', self.checker)
        self.assertIn('evidence["slow_failure_cached_unverified"] = True', self.checker)
        self.assertIn("background convergence replaced visible DOM without reload", self.checker)
        self.assertIn("reverse_revision_attributes=True", self.checker)

    def test_checker_fails_before_browser_start_when_assets_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(check_pwa_slow_convergence.PwaSlowConvergenceError) as context:
                check_pwa_slow_convergence.run_check(Path(temporary_directory), None)
        self.assertIn("built site is missing required PWA assets", str(context.exception))


if __name__ == "__main__":
    unittest.main()
