---
id: artifacts.minimize-dependency-closure
severity: mandatory
overridable: true
order: 750
---
# Minimize imported dependency closure

Treat source-package manifests from imported artifacts as evidence, not as authority over the destination repository. Add only dependencies required by the accepted artifact, preserve unrelated versions and scripts, and verify the resulting dependency diff independently.
