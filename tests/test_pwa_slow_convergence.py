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

    def test_background_task_registration_chains_all_registered_work(self) -> None:
        self.assertGreaterEqual(
            self.worker.count(
                "backgroundTask = Promise.all([backgroundTask, Promise.resolve(task)])"
            ),
            2,
        )
        self.assertNotIn("backgroundTask = Promise.resolve(task);", self.worker)

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

    def test_async_locale_loading_cannot_overwrite_network_commit(self) -> None:
        self.assertIn("let lastNetworkCommitGeneration = 0", self.client)
        self.assertIn("lastNetworkCommitGeneration = 0", self.client)
        self.assertIn("const strings = await currentPwaFreshnessStrings()", self.client)
        self.assertGreaterEqual(self.client.count("freshnessStateIsApplicable(data, normalizedUrl)"), 2)
        self.assertIn(
            "lastNetworkCommitGeneration >= data.requestGeneration",
            self.client,
        )
        self.assertIn(
            "lastNetworkCommitGeneration = Math.max(",
            self.client,
        )

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
        self.assertIn('"fixture-worker-instance-before-restart",\n            9', self.checker)
        self.assertIn('"fixture-worker-instance-after-restart",\n            1', self.checker)
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

    def test_fast_non_transient_4xx_never_records_verified_current(self) -> None:
        start = self.worker.index("async function handleCompletedDocumentNetwork")
        end = self.worker.index("async function convergeAfterChecking", start)
        handler = self.worker[start:end]
        fourxx_start = handler.index("if (response.status >= 400)")
        cacheable_start = handler.index("if (isCacheableDocumentResponse(response))", fourxx_start)
        branch = handler[fourxx_start:cacheable_start]
        self.assertIn("forgetRequestFreshnessStateThroughGeneration(event, generation)", branch)
        self.assertIn('notifyInstantNavigationCommit(event, "network", generation)', branch)
        self.assertIn("return response;", branch)
        self.assertNotIn('rememberFreshnessState(event, "verified-current"', branch)

    def test_background_completion_converges_by_robust_revision_extraction(self) -> None:
        self.assertIn("async function convergeAfterChecking(", self.worker)
        self.assertIn("function extractMetaAttributes(tag)", self.worker)
        self.assertIn("source.match(/<meta\\b[^>]*>/gi)", self.worker)
        read_start = self.worker.index("async function readSiteRevision(response)")
        read_end = self.worker.index("function startDocumentNetworkRequest", read_start)
        reader = self.worker[read_start:read_end]
        raw_text_index = reader.index("<(script|style)\\b")
        comment_index = reader.index("/<!--[\\s\\S]*?-->/g")
        head_index = reader.index("const headMatch")
        self.assertLess(raw_text_index, head_index)
        self.assertLess(comment_index, head_index)
        self.assertIn("previousRevision === nextRevision", self.worker)
        self.assertIn('"verified-current"', self.worker)
        self.assertIn('"update-available"', self.worker)
        self.assertIn('"cached-unverified"', self.worker)
        self.assertIn('evidence["reordered_meta_verified_current"] = True', self.checker)
        self.assertIn('evidence["missing_revision_update_available"] = True', self.checker)
        self.assertIn('evidence["non_html_update_available"] = True', self.checker)

    def test_background_state_delivery_is_client_scoped(self) -> None:
        self.assertNotIn('self.clients.matchAll({ type: "window" })', self.worker)
        self.assertIn("documentStateKey(client.url) !== targetKey", self.worker)
        self.assertIn(
            'if (!client || typeof client.postMessage !== "function") {\n    return !requireAcknowledgement;',
            self.worker,
        )
        self.assertIn(
            'normalizedUrl !== normalizedDocumentUrl(window.location.href)',
            self.client,
        )
        self.assertIn("requestCurrentFreshnessState();", self.client)
        self.assertIn('evidence["previous_document_convergence_ignored"] = True', self.checker)

    def test_client_specific_state_is_independent_of_document_generation(self) -> None:
        self.assertIn("const documentRemembered = rememberBounded(", self.worker)
        self.assertIn("const clientRemembered = clientId", self.worker)
        self.assertIn("return documentRemembered || clientRemembered;", self.worker)
        self.assertIn(
            "lastFreshnessGeneration = Math.max(\n        lastFreshnessGeneration,\n        pending.generation",
            self.client,
        )
        self.assertIn('evidence["newer_commit_retired_old_convergence"] = True', self.checker)

    def test_older_authoritative_absence_cannot_delete_newer_freshness_state(self) -> None:
        self.assertIn("function forgetFreshnessStateThroughGeneration(", self.worker)
        self.assertIn("function forgetRequestFreshnessStateThroughGeneration(", self.worker)
        self.assertIn("stored.generation <= generation", self.worker)
        self.assertIn(
            "forgetFreshnessStateThroughGeneration(\n    clientFreshnessStates",
            self.worker,
        )
        self.assertIn(
            "forgetFreshnessStateThroughGeneration(\n    documentFreshnessStates",
            self.worker,
        )

    def test_controllerchange_without_remembered_state_downgrades_checking(self) -> None:
        self.assertIn("currentState: typeof currentState === \"string\" ? currentState : null", self.client)
        self.assertIn('event.data.currentState === "checking"', self.worker)
        self.assertIn('state: "cached-unverified"', self.worker)
        self.assertIn("nextDocumentRequestGeneration = recoveryGeneration", self.worker)
        self.assertIn('evidence["controllerchange_missing_state_downgraded"] = True', self.checker)

    def test_verified_current_waits_for_correlated_cached_commit(self) -> None:
        self.assertIn('data.state === "verified-current"', self.client)
        self.assertIn('pending.representation === "cached"', self.client)
        self.assertIn("pending.generation === data.requestGeneration", self.client)
        self.assertIn('evidence["verified_current_waited_for_cached_commit"] = True', self.checker)
        self.assertIn("def _wait_for_cached_document_text(", self.checker)
        self.assertIn('_wait_for_cached_document_text(page, "document-v22")', self.checker)

    def test_interrupted_pending_commit_clears_previous_warning(self) -> None:
        self.assertIn("if (pending && committedUrl !== pending.url)", self.client)
        mismatch_start = self.client.index("if (pending && committedUrl !== pending.url)")
        mismatch_end = self.client.index("const embeddedStatus", mismatch_start)
        mismatch_branch = self.client[mismatch_start:mismatch_end]
        self.assertIn("clearFreshnessStatus();", mismatch_branch)
        self.assertIn("requestCurrentFreshnessState();", mismatch_branch)
        self.assertIn('evidence["interrupted_commit_warning_cleared"] = True', self.checker)

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
        self.assertIn("reload.textContent = strings.reload", self.client)
        self.assertNotIn('reload.textContent = "Reload"', self.client)
        self.assertIn("window.location.reload()", self.client)
        self.assertIn('type: "templates:get-current-freshness-state"', self.client)
        self.assertIn("lastFreshnessGeneration", self.client)
        self.assertIn("pendingDocumentCommit", self.client)
        self.assertIn('pending.representation === "cached"', self.client)
        self.assertIn("document.body || document.documentElement", self.client)
        self.assertIn("navigator.serviceWorker?.controller", self.client)
        self.assertIn('["checking", "cached-unverified", "update-available"].includes(', self.client)

    def test_chromium_checker_covers_convergence_edge_cases(self) -> None:
        self.assertIn('evidence["instant_checking"] = True', self.checker)
        self.assertIn('evidence["instant_update_available"] = True', self.checker)
        self.assertIn('evidence["slow_failure_cached_unverified"] = True', self.checker)
        self.assertIn("background convergence replaced visible DOM without reload", self.checker)
        self.assertIn("reverse_revision_attributes=True", self.checker)
        self.assertIn("FETCH_CHECK_TIMEOUT_MS = 10_000", self.checker)
        self.assertIn("document fetch did not settle within", self.checker)

    def test_checker_fails_before_browser_start_when_assets_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(check_pwa_slow_convergence.PwaSlowConvergenceError) as context:
                check_pwa_slow_convergence.run_check(Path(temporary_directory), None)
        self.assertIn("built site is missing required PWA assets", str(context.exception))


if __name__ == "__main__":
    unittest.main()
