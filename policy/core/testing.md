---
id: testing.run-required-checks
severity: mandatory
overridable: true
order: 300
---
# Run the repository's required verification

Use the verification command declared by the repository and add focused checks needed for the changed behavior or failure mode. Confirm that the executed checks cover the changed surface and the current revision; a check that is pending, skipped, not triggered, stale, blocked, or merely inspected is not a passing result. Report every required check that was not run or did not pass.

A validation claim is supported only when the claimed check is reachable from and actually executed by the authoritative validation entrypoint used to produce the evidence. A helper or test file existing beside a green workflow is not evidence that its assertions ran. Establish the effective path through workflow selection, canonical checker or test discovery, helper invocation, and the claimed assertion, including material conditions that can skip it. A module outside test discovery, an uncalled wrapper, an unused generated validation projection, or an assertion executed only in an optional/non-required lane cannot substantiate a claim of coverage by the required lane. Successful unrelated checks do not fill that gap.

Use repository-appropriate evidence such as source inspection with execution results, test discovery, workflow wiring tests, or runtime markers; universal static call-graph tooling is not required. Reachability alone is not a passing result: establish execution and the claimed outcome for the applicable revision, configuration, and evidence layer. If the effective path or execution cannot be established, report that coverage as unverified rather than accepting a green aggregate result.
