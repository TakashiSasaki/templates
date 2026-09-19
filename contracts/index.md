# Site contracts

## Publication and runtime boundaries

- [Contract manifest](manifest.json) - Declares the Site-owned contract inventory and source relationships.
- [Site discovery contract](site-discovery.json) - Defines deployed metadata, robots, sitemap, and feed surfaces.
- [Publication support](site-publication-support.json) - Declares the Site-side Bundle feature support boundary.
- [Bundle consumer contract](publication-bundle/README.md) - Documents the Site-side immutable Bundle reader boundary.

## Progressive discovery

- [Progressive discovery source](../progressive-discovery.json) - Supplies Site-owned labels and semantic document identities for the generated Markdown entry point.
- [Progressive discovery schema](../schemas/progressive-discovery.schema.json) - Validates that source entries use deployed routes or Bundle document identities rather than repository source paths.
