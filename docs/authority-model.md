# Authority model

Policy, Composition, Modeling, Integration and Site have independent Git histories.
Providers own meaning and export catalogs. Integration snapshots provider branches
and publishes semantic artifacts. Site consumes a complete artifact and owns routes,
navigation, styling and Pages deployment. Source only flows downstream.

The `/use/` surface serves consumers. The `/maintain/` surface serves providers and
maintainers. Site's `surfaces.json` controls their presentation. Adding a provider
means registering its branch in Integration; adding a document means editing its
provider catalog. Neither operation requires a Site pin update.
