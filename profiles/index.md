# Policy profile navigation

## Selectable profiles

- [Core](core.yml) - Baseline repository-change and validation policy selected explicitly by consumers.
- [External artifact intake](external-artifact-intake.yml) - Policy for bounded external-artifact intake.
- [Progressive discovery](progressive-discovery.yml) - Optional semantic policy for maintaining index.md navigation.
- [Pull request](pull-request.yml) - Policy for exact-head review, CI, and PR completion.
- [Review](review.yml) - Policy for independent review and finding quality.
- [Security baseline](security-baseline.yml) - Baseline secret and input-validation policy.

## Composition guidance

- [Shared policy corpus](../policy/index.md) - Routes from profiles to the atomic rule families they select.
- [Profile documentation](../docs/shared-policy/profiles.md) - Explains explicit selection and context composition.
