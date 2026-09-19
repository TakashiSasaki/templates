from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-pages.yml"
PRODUCER_WORKFLOW = ROOT / ".github/workflows/site-producer.yml"
SOURCE_LOCK = ROOT / "publication-sources.json"


class PagesWorkflowBoundaryTests(unittest.TestCase):
    def test_reusable_workflow_remains_non_deploying_and_browser_check_is_pr_only(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
        trigger_block = workflow.split("\npermissions:\n", maxsplit=1)[0]
        build_block, check_block = workflow.split("\n  check:\n", maxsplit=1)

        self.assertIn("  pull_request:\n", trigger_block)
        self.assertNotIn("branches:", trigger_block)
        self.assertIn("  workflow_call:", trigger_block)
        self.assertNotIn("\n  push:\n", trigger_block)
        self.assertNotIn("composition_ref:", workflow)
        self.assertNotIn("skill_ref:", workflow)
        self.assertNotIn("webapp_ref:", workflow)
        self.assertNotIn("source_ref:", workflow)
        self.assertIn("uses: ./.github/workflows/site-producer.yml", build_block)
        self.assertIn("actions/upload-pages-artifact@", PRODUCER_WORKFLOW.read_text())
        self.assertNotIn("actions/download-artifact@", build_block)
        self.assertNotIn("actions/configure-pages@", workflow)
        self.assertNotIn("actions/deploy-pages@", workflow)
        self.assertNotIn("pages: write", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("\n  deploy:\n", workflow)

        self.assertIn("always() &&", check_block)
        self.assertIn("github.event_name == 'pull_request'", check_block)
        self.assertIn("inputs.site_ref == ''", check_block)
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            check_block,
        )
        self.assertIn("needs:\n      - build\n      - classify_browser", check_block)
        self.assertIn("BUILD_RESULT: ${{ needs.build.result }}", check_block)
        self.assertIn(
            "CLASSIFIER_RESULT: ${{ needs.classify_browser.result }}",
            check_block,
        )
        self.assertIn(
            "BROWSER_REQUIRED: ${{ needs.classify_browser.outputs.browser_required }}",
            check_block,
        )
        self.assertIn("test \"$BUILD_RESULT\" = success", check_block)
        self.assertIn("test \"$CLASSIFIER_RESULT\" = success", check_block)
        self.assertIn("scripts/consume_site_build_artifact.py", check_block)
        self.assertIn("needs.build.outputs.artifact_digest", check_block)
        self.assertIn("needs.classify_browser.outputs.site_candidate == 'true'", check_block)

    def test_browser_classifier_is_exact_head_fail_closed_and_parallel_to_build(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
        build_block, remainder = workflow.split("\n  classify_browser:\n", maxsplit=1)
        classifier_block, check_block = remainder.split("\n  check:\n", maxsplit=1)

        classify_workflow = (ROOT / ".github/workflows/classify.yml").read_text(encoding="utf-8")

        self.assertIn("actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9", PRODUCER_WORKFLOW.read_text())
        self.assertNotIn("needs: build", classifier_block)
        self.assertIn("name: Classify browser acceptance scope", classifier_block)
        self.assertTrue(
            "uses: ./.github/workflows/classify.yml" in classifier_block
            or "scripts/classify_site_ci.py" in classifier_block
        )
        self.assertIn(
            "ref: ${{ inputs.candidate_ref || github.event.pull_request.head.sha || github.sha }}",
            classify_workflow,
        )
        self.assertIn(
            "candidate_ref: ${{ inputs.deployment_revision || inputs.site_ref || github.event.pull_request.head.sha || github.sha }}",
            classifier_block,
        )
        self.assertIn("fetch-depth: 0", classify_workflow)
        self.assertIn("persist-credentials: false", classify_workflow)
        self.assertNotIn("actions/setup-python", classify_workflow)
        self.assertNotIn("python-version", classify_workflow)
        self.assertNotIn("Collect exact pull-request changed paths", classify_workflow)
        self.assertNotIn("test -s \"$RUNNER_TEMP/site-browser-paths.txt\"", classify_workflow)
        self.assertIn(
            "python3 scripts/collect_site_changed_paths.py \\",
            classify_workflow,
        )
        self.assertIn("base-diff-unavailable-full", classify_workflow)
        self.assertIn("valid-empty-pull-request-diff", classify_workflow)
        self.assertIn("write_full_outputs", classify_workflow)
        self.assertIn("boundary_status=0", classify_workflow)
        self.assertIn('"$boundary_status" -eq 20', classify_workflow)
        self.assertIn('"$boundary_status" -eq 21', classify_workflow)
        self.assertIn("base-classification-unavailable-full", classify_workflow)
        self.assertIn("--changed-paths \"$changed_paths\"", classify_workflow)
        self.assertIn("git show \"$BASE_SHA:scripts/classify_site_ci.py\"", classify_workflow)
        self.assertIn("python3 -I \"$classifier_dir/classify_site_ci.py\"", classify_workflow)
        self.assertNotIn("python3 -I scripts/classify_site_browser_acceptance.py", classify_workflow)
        self.assertNotIn("python3 -I scripts/classify_site_ci.py", classify_workflow)
        self.assertIn("authority_source=\"base-unavailable-full\"", classify_workflow)
        self.assertIn("browser_required: ${{ steps.classify.outputs.browser_required }}", classify_workflow)
        self.assertIn("site_candidate: ${{ steps.classify.outputs.site_candidate }}", classify_workflow)
        self.assertNotIn("required: ${{ steps.classify.outputs.required }}", classify_workflow)
        self.assertIn("reason: ${{ steps.classify.outputs.reason }}", classify_workflow)

        self.assertIn("Unexpected browser acceptance classification", check_block)
        self.assertIn(
            "if: ${{ needs.classify_browser.outputs.browser_required == 'true' }}",
            check_block,
        )
        self.assertIn(
            "if: ${{ always() && needs.classify_browser.outputs.browser_required == 'true' }}",
            check_block,
        )

    def test_browser_heavy_steps_are_guarded_by_classifier_output(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
        check_block = workflow.split("\n  check:\n", maxsplit=1)[1]
        required_condition = "if: ${{ needs.classify_browser.outputs.browser_required == 'true' }}"

        heavy_steps = (
            "Check out proposed Site revision",
            "Verify and consume scheduled Pages artifact",
            "Install Playwright controller",
            "Verify system Chrome runtime",
            "Install Japanese browser font",
            "Check mobile layout geometry",
            "Check localized inline Glossary chrome",
            "Check PWA freshness lifecycle",
            "Check localized PWA freshness chrome",
            "Check PWA document commit correlation",
            "Check PWA slow-network convergence",
            "Check PWA freshness capability messaging",
            "Check Site search history",
            "Check review regressions for Site search history",
        )
        pwa_steps = {
            "Check PWA freshness lifecycle",
            "Check localized PWA freshness chrome",
            "Check PWA document commit correlation",
            "Check PWA slow-network convergence",
            "Check PWA freshness capability messaging",
        }
        pwa_condition = "if: ${{ needs.classify_browser.outputs.browser_required == 'true' && (needs.classify_browser.outputs.pwa_required == 'true' || needs.classify_browser.outputs.full_required == 'true') }}"

        for index, step_name in enumerate(heavy_steps):
            with self.subTest(step=step_name):
                marker = f"      - name: {step_name}\n"
                start = check_block.index(marker) + len(marker)
                next_step = check_block.find("\n      - name:", start)
                step_body = check_block[start:] if next_step == -1 else check_block[start:next_step]
                expected_condition = pwa_condition if step_name in pwa_steps else required_condition
                priority = {"Check mobile layout geometry": "layout", "Check Site search history": "search",
                            "Check PWA freshness lifecycle": "pwa"}.get(step_name)
                if priority:
                    expected_condition = expected_condition.replace(" }}", f" && steps.priority_{priority}.outcome != 'success' }}}}")
                self.assertIn(expected_condition, step_body)

        for evidence_step in (
            "Upload mobile visual evidence",
            "Upload search-history evidence",
        ):
            with self.subTest(step=evidence_step):
                marker = f"      - name: {evidence_step}\n"
                start = check_block.index(marker) + len(marker)
                next_step = check_block.find("\n      - name:", start)
                step_body = check_block[start:] if next_step == -1 else check_block[start:next_step]
                self.assertIn(
                    "if: ${{ always() && needs.classify_browser.outputs.browser_required == 'true' }}",
                    step_body,
                )



    def test_site_dispatch_workflow_is_the_only_deployment_authority(self) -> None:
        workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        trigger_block = workflow.split("\npermissions:\n", maxsplit=1)[0]

        self.assertIn(
            "  workflow_dispatch:",
            trigger_block,
        )
        self.assertNotIn("pull_request:", trigger_block)
        self.assertNotIn("workflow_call:", trigger_block)
        self.assertNotIn("  push:", trigger_block)
        self.assertIn("uses: ./.github/workflows/build-pages.yml", workflow)
        self.assertNotIn("site_ref:", workflow)  # dispatch qualifies the event SHA through the full DAG
        self.assertIn("github.repository == 'TakashiSasaki/templates'", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)
        self.assertIn("github.ref == 'refs/heads/site'", workflow)
        for required in (
            "vars.PUBLICATION_AUTOMATION_MODE == 'auto-publish'",
            "vars.PUBLICATION_AUTOMATION_AUTHORIZED == 'true'",
            "vars.PUBLICATION_POLICY_REVISION != ''",
            "vars.PUBLICATION_CONTROLLER_REVISION != ''",
            "vars.PUBLICATION_AUTOMATION_KILL_SWITCH != 'true'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, workflow)
        self.assertNotIn("github.event.repository.default_branch", workflow)

        reconcile = (ROOT / ".github/workflows/publication-reconcile.yml").read_text(encoding="utf-8")
        self.assertIn("id: trusted_receipt", reconcile)
        self.assertIn("MISSING_TRUSTED_INTEGRATION_RECEIPT", reconcile)
        self.assertIn("TRUSTED_RECEIPT_AVAILABLE", reconcile)
        self.assertIn(
            'if [ -d publication-bundle ] && [ "$TRUSTED_RECEIPT_AVAILABLE" = true ]; then',
            reconcile,
        )

        self.assertIn("TZ=Asia/Tokyo", workflow)
        self.assertIn("deployment_timestamp:", workflow)
        self.assertIn("needs: deployment_metadata", workflow)
        self.assertIn("- build", workflow)
        self.assertIn("artifact_gate", workflow)
        self.assertIn('QUALIFICATION_GATE: ${{ needs.build.outputs.qualification_gate }}', workflow)
        self.assertIn('test "$QUALIFICATION_GATE" = success', workflow)
        self.assertIn("inputs['publication_bundle']['identity']", workflow)
        verifier = (ROOT / "scripts/revalidate_pages_deployment.py").read_text(encoding="utf-8")
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("name: github-pages", workflow)
        self.assertIn("actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d", workflow)
        self.assertIn("actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346", workflow)
        self.assertIn("artifact_name: github-pages", workflow)
        self.assertIn("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", workflow)
        self.assertIn("ref: ${{ github.workflow_sha }}", workflow)
        self.assertIn("sparse-checkout: scripts/revalidate_pages_deployment.py", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("git -C .trusted-deployment-verifier rev-parse HEAD", workflow)
        self.assertIn("python3 .trusted-deployment-verifier/scripts/revalidate_pages_deployment.py", workflow)
        self.assertNotIn("except subprocess.CalledProcessError", workflow)
        self.assertNotIn("repository_variable('PUBLICATION_AUTOMATION_KILL_SWITCH', 'false')", workflow)
        self.assertIn("\n  deploy:\n", workflow)
        self.assertIn(
            "Revalidate publication preconditions immediately before Pages deployment",
            workflow,
        )
        self.assertIn("actions/variables/{name}", verifier)
        self.assertIn("Site branch advanced before Pages deployment", verifier)
        self.assertLess(
            workflow.index("Revalidate publication preconditions immediately before Pages deployment"),
            workflow.index("Configure GitHub Pages"),
        )

        metadata = workflow.index("  deployment_metadata:")
        build = workflow.index("  build:")
        deploy = workflow.index("  deploy:")
        self.assertLess(metadata, build)
        self.assertLess(build, deploy)

    def test_manual_shadow_dispatch_and_automatic_dispatch_have_distinct_gates(self) -> None:
        import yaml

        workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
        inputs = workflow[True]["workflow_dispatch"]["inputs"]
        self.assertEqual(inputs["automatic"]["type"], "boolean")
        self.assertFalse(inputs["automatic"]["default"])
        text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("inputs.automatic != true", text)
        self.assertIn("inputs.automatic == true", text)
        self.assertIn("trusted_release_required: ${{ inputs.automatic == true }}", text)
        self.assertIn("Human dispatch is the authorization for the manual lane", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("BUILD_RECEIPT: ${{ needs.build.outputs.bundle_receipt }}", text)
        self.assertIn("EXPECTED_KILL_SWITCH: ${{ vars.PUBLICATION_AUTOMATION_KILL_SWITCH || 'false' }}", text)
        self.assertIn("the automatic build did not carry a trusted Integration receipt", (ROOT / "scripts/revalidate_pages_deployment.py").read_text(encoding="utf-8"))
        self.assertIn("trusted receipt and final artifact selected different Bundle inputs", (ROOT / "scripts/revalidate_pages_deployment.py").read_text(encoding="utf-8"))
        self.assertIn("-f \"automatic=true\"", (ROOT / ".github/workflows/site-publication-notify.yml").read_text(encoding="utf-8"))
        jobs = workflow["jobs"]
        for name, job in jobs.items():
            permissions = job.get("permissions", {})
            if name == "deploy":
                self.assertEqual(permissions.get("pages"), "write")
                self.assertEqual(permissions.get("id-token"), "write")
            else:
                self.assertNotIn("pages", permissions)
                self.assertNotIn("id-token", permissions)

    def test_aggregate_ci_validate_gate_and_force_full_qualification(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
        classify_workflow = (ROOT / ".github/workflows/classify.yml").read_text(encoding="utf-8")
        self.assertIn("name: Site Construction CI / validate", workflow)
        self.assertIn("needs:\n      - build\n      - classify_browser\n      - check\n      - core_tests", workflow)
        self.assertIn("test \"$CORE_TESTS_RESULT\" = success", workflow)
        self.assertIn("python3 scripts/run_core_tests.py", workflow)
        self.assertTrue(
            "FORCE_FULL_REQUESTED:" in workflow or "FORCE_FULL_REQUESTED:" in classify_workflow
        )
        self.assertTrue(
            "--force-full" in workflow or "--force-full" in classify_workflow
        )
        self.assertIn("ci/full-qualification", workflow)

    def test_forked_pull_requests_retain_conservative_build(self) -> None:
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
        build_block = workflow.split("\n  classify_browser:\n", maxsplit=1)[0]
        self.assertIn(
            "github.event.pull_request.head.repo.full_name != github.repository",
            build_block,
        )

    def test_labeled_trigger_is_gated_on_qualification_labels(self) -> None:
        import yaml
        workflow_data = yaml.safe_load(BUILD_WORKFLOW.read_text(encoding="utf-8"))
        jobs = workflow_data["jobs"]
        for job_key in ("build", "classify_browser", "check", "core_tests", "validate"):
            with self.subTest(job=job_key):
                self.assertIn(job_key, jobs)
                job_if = jobs[job_key].get("if", "")
                self.assertIn("github.event.action != 'labeled'", job_if)
                self.assertIn("ci/full-qualification", job_if)
                self.assertIn("ci/full-site-verification", job_if)


    def test_dispatcher_owns_label_concurrency(self) -> None:
        import yaml
        workflow = yaml.safe_load(BUILD_WORKFLOW.read_text())
        self.assertIn('labeled', workflow[True]['pull_request']['types'])
        for token in ('unrelated-label-', 'ci/full-qualification', 'ci/full-site-verification', 'ci/browser', 'github.run_id'):
            self.assertIn(token, workflow['concurrency']['group'])
        for name in ('reference-consumer.yml', 'site-composition-playground-cross-authority.yml', 'site-producer.yml'):
            worker = yaml.safe_load((BUILD_WORKFLOW.parent / name).read_text())
            self.assertIn('workflow_call', worker[True])
            self.assertNotIn('pull_request', worker[True])
            self.assertNotIn('concurrency', worker)


if __name__ == "__main__":
    unittest.main()
