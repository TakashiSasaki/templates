<!--
agent-policy-generated: true
source-skill: title-conversation-session
DO NOT EDIT DIRECTLY
-->
---
name: title-conversation-session
description: Finalize truthful, outcome-oriented conversation-session titles on compatible interaction surfaces without treating title metadata as work authority.
---

# Title Conversation Sessions

Use this Skill only when the active interaction surface has a conversation/session concept, or an equivalent user-visible container for which a title can be persisted or presented. This is an interaction-surface procedure, not shared semantic policy. If the Skill is selected but the active surface has no meaningful title concept, do nothing.

## 1. Determine whether a title is due

Produce a title when the user explicitly requests one, or when a substantial work session reaches an established terminal boundary. Terminal boundaries include completion of the requested work, completion of an explicitly requested final action such as merge or deployment, an authorized human handoff or other stop boundary, and an explicit user declaration that the session is finished. A substantial design, architecture, audit, analysis, or planning session may likewise receive a title when it reaches a stable conclusion or produces a handoff or continuation plan.

Do not finalize a title merely because an intermediate implementation step, branch, commit, individual pull request, progress report, CI run, or review event occurred while the session is expected to continue. When the user explicitly requests a title before a terminal boundary, describe only the state established so far; do not imply that the session itself is complete.

## 2. Describe the observed outcome

Base the title on what actually happened rather than merely restating the initial objective. Include enough of the principal object or subsystem and the principal action or result to distinguish the session from nearby work. Include a terminal-state cue when it materially improves disambiguation.

Do not imply completion, merge, deployment, review completion, handoff readiness, or another state unless the applicable evidence and completion semantics establish that state. Prefer concrete outcome terms such as implementation, remediation, validation, audit, deployment, merge, review handoff, design, or investigation. A compact status prefix may be used when the interaction convention supports one, but it must encode established state rather than topic alone.

Use the interaction's established language and naming conventions unless the user requests another format.

## 3. Deliver through a compatible surface only

Evaluate the active surface before attempting delivery:

1. If the surface exposes an authorized title-persistence mechanism and its use is permitted, persist the title through that mechanism.
2. Otherwise, if the surface permits free-form presentation in the current or terminal response, present the same text as a title proposal.
3. Otherwise, omit title output rather than violating a fixed response schema, protocol contract, or other surface constraint.

Do not invent a persistence API, assume a provider-specific command, or encode title metadata into an unrelated field. Failure or absence of a persistence/presentation mechanism must not change the established work state, reopen completed work, block an otherwise valid handoff or completion boundary, or justify a false completion claim.

## Authority boundary

Treat the title as presentation and navigation metadata only. It is not repository state, validation evidence, review evidence, merge authorization, deployment evidence, or completion authority. Repository and workflow state must be established and reported through their applicable authorities independently of this Skill.
