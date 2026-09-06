# Routes v4 to v5: directory-style canonical URLs

Routes v5 adds one optional trailing slash to non-root canonical paths and aliases.
This permits adoption of existing documentation websites without renaming their
real public URLs. The root remains `/`; repeated separators, dot segments,
backslashes, percent encoding, queries, fragments, and non-ASCII segments remain
invalid. `/guide` and `/guide/` remain distinct paths. No redirect or equivalence
is inferred: consumers declare any supported alias explicitly and implement it.

The change is owned by `foundation.web` version 3, shared by Website and Webapp.
Use an explicit Composition upgrade to cross that component boundary, then update
the consumer-owned routes worksheet to `schemaVersion: 5`. Existing v4 path values
retain their meanings; add a trailing slash only when that is the product's actual
canonical URL. Run the selected Composition validators and real route/browser
acceptance. No Site-specific mode or alternate resolver is introduced.
