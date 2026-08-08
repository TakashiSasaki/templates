---
id: skill-source.run-distribution-validation
severity: mandatory
overridable: true
order: 1040
---
# Run the Skill source and distribution validation baseline

For changes that can affect the source/distribution boundary, run at least:

```sh
ruby .github/scripts/test-distribution-boundary.rb
ruby .github/scripts/test-skill-distribution.rb
ruby .github/scripts/validate-skill-distribution.rb
python template/.github/scripts/validate_skill_repository.py template
python template/.github/scripts/test_template_baseline.py
ruby .github/scripts/test-copyable-template-consumption.rb
```

The Python validation host requires Python 3.12 or newer, PyYAML 6.0.3, and Git. Run additional profile-specific regression tests when the affected profile requires them. Networked or executable profile changes require real fixture and negative-path evidence, not only Markdown checks.
