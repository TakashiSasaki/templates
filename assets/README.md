# Skill assets

This directory is optional. Place static files used or produced by the workflow here, such as:

- document and message templates;
- configuration skeletons;
- sample input or output files;
- style, schema, or layout resources;
- images or other media included in generated artifacts;
- fixtures that are operationally reused rather than maintained only for tests.

Assets are not automatically instructions. For every retained asset, `SKILL.md` or a directly linked reference must state:

- when the asset is used;
- whether it is copied, filled, transformed, compared, attached, or emitted;
- which parts may be modified;
- which parts must remain unchanged;
- the expected output location or relationship;
- applicable licensing, attribution, confidentiality, or redistribution constraints;
- validation required after transformation.

Do not store secrets or environment-specific credentials in assets. Distinguish illustrative samples from authoritative templates so the agent does not treat example values as real configuration.

Keep test-only fixtures under the selected test layout unless the same file is also an operational skill resource.

Delete this directory when the concrete skill has no static operational resources.
