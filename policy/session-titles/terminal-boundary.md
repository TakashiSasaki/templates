---
id: session-titles.generate-at-terminal-boundary
severity: mandatory
overridable: false
order: 1100
---
# Generate session titles at meaningful terminal boundaries

When this profile is selected, produce a conversation-session title when the user explicitly requests one or when a substantial work session reaches an established terminal boundary. Terminal boundaries include completion of the requested work, completion of an explicitly requested final action such as merge or deployment, an authorized human-handoff or other stop boundary, and an explicit user declaration that the session is finished. A substantial design, architecture, audit, analysis, or planning session should likewise receive a title when it reaches a stable conclusion or produces a handoff or continuation plan.

Do not finalize a session title merely because an intermediate implementation step, branch, commit, individual pull request, progress report, CI run, or review event occurred while the session is expected to continue. Prefer finalizing the title at the terminal boundary rather than at session start so the title can describe the work that actually occurred; a provisional working title may be refined when the terminal state is known.
