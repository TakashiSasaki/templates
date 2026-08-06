#!/usr/bin/env ruby
# frozen_string_literal: true

require "pathname"

ROOT = Pathname.new(File.expand_path("..", __dir__))
failures = []

required = %w[
  SKILL.md
  README.md
  AGENTS.md
  .github/scripts/validate-skill-repository.rb
  .github/scripts/validate-profile-contracts.rb
]
required.each do |relative|
  path = ROOT.join(relative)
  failures << "missing required Skill-root file: #{relative}" unless path.file? && !path.symlink?
end

forbidden = %w[
  template
  distribution-manifest.json
  CHANGELOG.md
  CONTRIBUTING.md
  docs/publication-catalog.json
  docs/publication-maintenance.md
  docs/architecture/distribution-boundary.md
  docs/architecture/distribution-classification.json
  .github/REVIEW_GUIDELINES.md
  .github/fixtures
  .github/workflows/pages.yml
  .github/workflows/validate-structure.yml
  .github/workflows/validate-portable-consumption.yml
  .github/workflows/validate-extended-profile-contracts.yml
]
forbidden.each do |relative|
  path = ROOT.join(relative)
  failures << "source-maintainer path leaked into Skill distribution: #{relative}" if path.exist? || path.symlink?
end

skill_path = ROOT.join("SKILL.md")
if skill_path.file?
  skill = skill_path.read(encoding: "UTF-8")
  selections = skill.lines.grep(/^Selected profiles:/)
  failures << "SKILL.md must contain exactly one Selected profiles line" unless selections.length == 1

  if selections.first&.strip == "Selected profiles: template-scaffold"
    readme = ROOT.join("README.md").read(encoding: "UTF-8")
    unless readme.include?("# Language-neutral Agent Skill Template") &&
           readme.include?("This repository is a template for developing a portable Agent Skill")
      failures << "uncustomized template must retain its canonical README identity"
    end
    failures << "uncustomized template must retain LICENSE.template" unless ROOT.join("LICENSE.template").file?
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Agent Skill template-root boundary is valid."
