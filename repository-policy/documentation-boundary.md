---
id: policy-repo.preserve-documentation-deployment-boundary
severity: mandatory
overridable: false
order: 1060
---
# Keep policy documentation build-only

The `policy` branch may validate and build its documentation but must not upload a GitHub Pages artifact, request Pages write authority, or deploy the site. Repository-site assembly and deployment belong to the unrelated `site` branch. Keep policy documentation workflows read-only except for permissions independently required by a reviewed maintenance task.
