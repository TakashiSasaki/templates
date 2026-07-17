# Bootstrap model

The unrelated `bootstrap-agent-policy` branch is a directly installable skill package. It contains no policy compiler logic. It reads a manifest that pins a `main` commit, invokes that revision's `agent-policy init`, and then transfers control to the initialized repository's manifest, lock file, generated skills, and CI.
