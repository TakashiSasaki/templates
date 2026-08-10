#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "pathname"
require "set"

ROOT = Pathname.new(File.expand_path("../..", __dir__))
failures = []

required_source_files = %w[
  README.md
  AGENTS.md
  CONTRIBUTING.md
  CHANGELOG.md
  LICENSE
  distribution-manifest.json
  docs/architecture/distribution-boundary.md
  docs/architecture/distribution-classification.json
  docs/publication-catalog.json
  docs/publication-maintenance.md
  maintainer/README.md
  template/SKILL.md
  template/README.md
  template/AGENTS.md
].freeze
required_source_files.each do |relative|
  path = ROOT.join(relative)
  failures << "missing required source artifact: #{relative}" unless path.file? && !path.symlink?
end

forbidden_root_skill_paths = %w[
  SKILL.md
  RUNTIME.md
  INTERFACES.md
  CLI_INTERFACE.md
  MCP_INTERFACE.md
  MCP_APPS.md
  WEB_INTERFACE.md
  LICENSE.template
  assets
  examples
  mcp
  references
  scripts
  src
  tests
].freeze
forbidden_root_skill_paths.each do |relative|
  path = ROOT.join(relative)
  failures << "obsolete root Skill authority reintroduced: #{relative}" if path.exist? || path.symlink?
end

canonical_validator_relatives = %w[
  lib/core_profile_interfaces.py
  lib/core_profile_runtime.py
  lib/profile_contracts.py
  validate_bundled_mcp_client_consistency.py
  validate_cli_exit_code_contract.py
  validate_cli_structured_output_contract.py
  validate_concrete_profile_consistency.py
  validate_core_profile_contracts.py
  validate_decomposed_interface_contracts.py
  validate_extended_profile_contracts.py
  validate_interface_routing_contract.py
  validate_interface_runtime_consistency.py
  validate_interface_summary_details.py
  validate_late_review_contracts.py
  validate_mcp_extensions.py
  validate_mcp_protocol_conformance.py
  validate_mcp_runtime_authority.py
  validate_profile_contracts.py
  validate_review_followup_contracts.py
  validate_selected_contract_scalar_placeholders.py
  validate_skill_repository.py
].freeze
canonical_validator_relatives.each do |relative|
  canonical = ROOT.join("template/.github/scripts", relative)
  legacy = ROOT.join(".github/scripts", relative)
  failures << "canonical downstream validator is missing: #{relative}" unless canonical.file? && !canonical.symlink?
  failures << "alternate root validator authority reintroduced: #{relative}" if legacy.exist? || legacy.symlink?
end

begin
  manifest = JSON.parse(ROOT.join("distribution-manifest.json").read(encoding: "UTF-8"))
  failures << "distribution manifest schema must remain canonical-inventory v2" unless manifest["schema_version"] == 2
  failures << "distribution manifest must not regain mirrors" if manifest.key?("mirrors")
  failures << "distribution manifest must not regain distribution_owned_files" if manifest.key?("distribution_owned_files")
  failures << "distribution manifest must declare canonical distribution_files" unless manifest["distribution_files"].is_a?(Array)
rescue JSON::ParserError, Errno::ENOENT => e
  failures << "invalid distribution manifest: #{e.message}"
end

begin
  classification = JSON.parse(ROOT.join("docs/architecture/distribution-classification.json").read(encoding: "UTF-8"))
  top_level = classification.fetch("topLevelClassification")
  failures << "template must remain the sole distribution root" unless top_level["distribution"] == ["template"]
  failures << "completed separation must have no split top-level entries" unless top_level["split"] == []
  failures << "maintainer directory must be source-owned" unless top_level.fetch("maintainer", []).include?("maintainer")

  profile = classification.fetch("profileModel")
  failures << "template marker changed" unless profile["templateMarker"] == "template-scaffold"
  failures << "exclusive profile set changed" unless profile["exclusiveProfiles"] == ["instruction-only"]
  expected_composable = %w[
    asset-driven
    browser-interface
    headless-service
    knowledge-augmented
    mcp-enabled
    packaged-cli
    script-assisted
  ]
  failures << "composable profile set changed" unless profile["composableProfiles"] == expected_composable
  failures << "profile composition rule changed" unless profile["compositionRule"] == "union-of-required-contracts"
rescue KeyError, JSON::ParserError, Errno::ENOENT => e
  failures << "invalid distribution classification: #{e.message}"
end

begin
  catalog = JSON.parse(ROOT.join("docs/publication-catalog.json").read(encoding: "UTF-8"))
  documents = catalog.fetch("documents")
  expected_ids = %w[
    overview
    skill-contract
    skill-profiles
    profile-contract-map
    runtime-decision-record
    interface-routing
    packaged-cli-interface
    mcp-interface
    mcp-apps-interface
    human-web-interface
    architecture
    runtime-selection
    mcp-transports
    mcp-apps-guidance
  ]
  actual_ids = documents.map { |document| document.fetch("id") }
  failures << "stable publication document IDs changed" unless actual_ids == expected_ids

  documents.each do |document|
    source = document.fetch("source")
    source_path = ROOT.join(source)
    failures << "publication source is missing: #{source}" unless source_path.file? && !source_path.symlink?
    if document.fetch("id") == "overview"
      failures << "overview must remain the source-product README" unless source == "README.md"
    elsif !source.start_with?("template/")
      failures << "consumer publication source escapes template/: #{source}"
    end
  end
rescue KeyError, JSON::ParserError, Errno::ENOENT => e
  failures << "invalid publication catalog: #{e.message}"
end

root_readme = ROOT.join("README.md").read(encoding: "UTF-8") rescue ""
[
  "The canonical user-facing artifact and its canonical source tree are `template/`.",
  "cp -a template/. /path/to/new-skill/",
  "The branch root deliberately contains no `SKILL.md`"
].each do |snippet|
  failures << "source README omits completed boundary: #{snippet.inspect}" unless root_readme.include?(snippet)
end

template_readme = ROOT.join("template/README.md").read(encoding: "UTF-8") rescue ""
unless template_readme.include?("This repository is a template for developing a portable Agent Skill")
  failures << "template README lost its consumer identity"
end

boundary = ROOT.join("docs/architecture/distribution-boundary.md").read(encoding: "UTF-8") rescue ""
[
  "The branch root is not an installable Skill directory.",
  "The copyable distribution is `template/`, and `template/` is also the sole canonical source tree",
  "The structural separation is complete."
].each do |snippet|
  failures << "distribution boundary omits completion statement: #{snippet.inspect}" unless boundary.include?(snippet)
end
[
  "future `template/`",
  "After this migration",
  "Until the structural migration is merged",
  "The future `template/` tree",
  "The intended source layout"
].each do |stale|
  failures << "distribution boundary retains transitional wording: #{stale.inspect}" if boundary.include?(stale)
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Skill template restructuring completion audit passed."
