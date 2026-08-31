# PWA update contract v1 to v2

Version 2 removes Webapp UI-state identifiers from PWA update semantics. The capability now records observable update detection and caller-visible presentation obligations without depending on a particular artifact's state vocabulary.

Recompose pre-production consumers from the current recipe revision, then map fields as follows:

| v1 field | v2 representation |
| --- | --- |
| implicit update detection | `updateDetection: "observable"` |
| `updateAvailableStateId` | `updateAvailablePresentation: "required-visible"` for `user-confirmed` activation |
| `applyingStateId` | optional `applyingUpdatePresentation: "required-visible"` |
| `failureStateId` | optional `failedUpdatePresentation: "required-visible"` |

`activation` and `unsavedChangesPolicy` retain their meanings. Immediate activation still cannot claim `block-activation` for unsaved work.
