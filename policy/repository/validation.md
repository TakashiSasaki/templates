---
id: skill-source.run-distribution-validation
severity: mandatory
overridable: true
order: 1040
---
# Run the Skill source and distribution validation baseline

For changes that can affect the source/distribution boundary, run at least:

```sh
python .github/scripts/test_distribution_boundary.py
python .github/scripts/test_skill_distribution.py
python .github/scripts/validate_skill_distribution.py
python template/.github/scripts/validate_skill_repository.py template
python template/.github/scripts/test_template_baseline.py
python .github/scripts/test_copyable_template_consumption.py
```

The Python validation host requires Python 3.12 or newer, PyYAML 6.0.3, and Git. Run additional profile-specific regression tests when the affected profile requires them. Networked or executable profile changes require real fixture and negative-path evidence, not only Markdown checks.
