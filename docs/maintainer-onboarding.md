# Maintain templates

Choose the owning authority and work in its independent branch/worktree:

| Change | Authority | Local validation |
| --- | --- | --- |
| Information-model records | Modeling | `python tools/qualify.py` |
| Components, recipes, Composer | Composition | `python scripts/run_composition_preflight.py fast` |
| Shared agent rules or compiler | Policy | `python -m pytest` |
| Catalog integration and semantic Bundles | Integration | `python -m unittest discover -s tests -v` |
| Documentation appearance, browser and Pages | Site | `python -m unittest discover -s tests -v` |

Each branch's `AGENTS.md` and README describe its commands. No branch adopts another
branch's maintenance policy implicitly. Keep all five histories unrelated. A downstream
failure does not block source implementation or mandate a cross-authority PR stack.

[Preview Site](../MAINTENANCE.md) using a downloaded publication. [Publish](../PUBLISHING.md)
by consuming successful Integration artifacts. Add provider documents in the owning catalog;
Integration includes them automatically; Site owns the public routes and navigation.
