#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require_relative "lib/profile_contracts"

include ProfileContracts

begin
  skill = SkillDocument.read("SKILL.md")
  selection = ProfileSelection.load("SKILL.md", document: skill)
rescue ParseError => e
  warn e.message
  exit 1
end

selected_profiles = selection.profiles
template_scaffold = selection.template_scaffold?
repository = RepositorySnapshot.new
errors = []

allowed_profiles = %w[
  instruction-only
  knowledge-augmented
  asset-driven
  script-assisted
  packaged-cli
  mcp-enabled
  browser-interface
  headless-service
].freeze

name = skill.metadata["name"]
description = skill.metadata["description"].to_s

if template_scaffold
  unless name == "agent-skill-template"
    warn "'template-scaffold' is valid only for the uncustomized agent-skill-template."
    exit 1
  end
elsif selected_profiles.include?("template-scaffold")
  warn "'template-scaffold' cannot be combined with concrete skill profiles."
  exit 1
end

unless template_scaffold
  duplicates = selected_profiles.group_by(&:itself).select { |_profile, values| values.length > 1 }.keys
  errors << "SKILL.md contains duplicate selected profiles: #{duplicates.join(', ')}" unless duplicates.empty?

  invalid_profiles = selected_profiles - allowed_profiles
  errors << "SKILL.md contains unknown selected profiles: #{invalid_profiles.join(', ')}" unless invalid_profiles.empty?
end

profile_requirements = {
  "packaged-cli" => ["RUNTIME.md", "INTERFACES.md", "CLI_INTERFACE.md"],
  "mcp-enabled" => ["RUNTIME.md", "INTERFACES.md", "MCP_INTERFACE.md", "docs/mcp-transports.md"],
  "browser-interface" => ["RUNTIME.md", "WEB_INTERFACE.md"],
  "headless-service" => ["RUNTIME.md"]
}.freeze

resource_profile_requirements = {
  "references" => "knowledge-augmented",
  "assets" => "asset-driven",
  "scripts" => "script-assisted",
  "mcp" => "mcp-enabled"
}.freeze

if template_scaffold
  customized_directories = resource_profile_requirements.keys.select do |directory|
    repository.operational_file_present?(directory)
  end
  unless customized_directories.empty?
    errors << "'template-scaffold' cannot be retained after adding operational files under: #{customized_directories.join(', ')}."
  end
else
  if name == "agent-skill-template" || description.include?("Template scaffold")
    errors << "A concrete skill must replace the template name and description."
  end

  if selected_profiles.include?("instruction-only") && selected_profiles.length > 1
    errors << "'instruction-only' cannot be combined with resource, executable, or service profiles."
  end

  if /\bTODO\b/i.match?(skill.text)
    errors << "A concrete SKILL.md must not retain TODO placeholders."
  end

  [
    "## Purpose",
    "## Use this skill when",
    "## Workflow",
    "## Output requirements",
    "## Validation",
    "## Safety and approval"
  ].each do |heading|
    content = skill.section(heading)
    if content.nil? || content.strip.empty?
      errors << "A concrete SKILL.md requires non-empty content under '#{heading}'."
    end
  end

  selected_profiles.each do |profile|
    profile_requirements.fetch(profile, []).each do |required_path|
      errors << "Selected profile '#{profile}' requires contract file: #{required_path}" unless repository.file?(required_path)
    end
  end

  resource_profile_requirements.each do |directory, required_profile|
    next unless repository.operational_file_present?(directory)
    next if selected_profiles.include?(required_profile)

    errors << "Retained operational files under #{directory}/ require selected profile '#{required_profile}'."
  end

  supported_contracts = {
    "RUNTIME.md" => %w[script-assisted packaged-cli mcp-enabled browser-interface headless-service],
    "INTERFACES.md" => %w[packaged-cli mcp-enabled],
    "CLI_INTERFACE.md" => %w[packaged-cli],
    "MCP_INTERFACE.md" => %w[mcp-enabled],
    "WEB_INTERFACE.md" => %w[browser-interface]
  }.freeze
  supported_contracts.each do |path, profiles|
    next unless File.exist?(path)
    next unless (selected_profiles & profiles).empty?

    errors << "Retained contract #{path} is unsupported by the selected profiles."
  end
end

index_output, index_status = Open3.capture2e(
  "git", "ls-files", "--stage", "-z", "--", "references", "assets", "scripts"
)
if index_status.success?
  index_output.split("\0").each do |record|
    next if record.empty?

    match = record.match(/\A(\d+)\s+[0-9a-f]+\s+\d+\t(.+)\z/m)
    next unless match

    errors << "Operational resource gitlinks are not allowed: #{match[2]}" if match[1] == "160000"
  end
else
  errors << "Unable to inspect the Git index for operational resource gitlinks: #{index_output.strip}"
end

runtime_allowed_profiles = %w[script-assisted packaged-cli mcp-enabled browser-interface headless-service]
runtime_selected = (selected_profiles & runtime_allowed_profiles).any?
runtime = repository.document("RUNTIME.md")

if runtime_selected && runtime
  runtime_status = runtime.field("Selection status")
  unless runtime_status == "SELECTED"
    errors << "Selected runtime-backed profiles require 'Selection status: SELECTED' in RUNTIME.md."
  end

  primary = runtime.section("## Primary implementation")
  [
    "Language",
    "Runtime",
    "Minimum runtime version",
    "Dependency/package manager",
    "Project manifest",
    "Lockfile policy",
    "Source layout",
    "Supported operating systems"
  ].each do |item|
    unless ValuePolicy.resolved?(runtime.table_value(item, section: primary))
      errors << "RUNTIME.md requires a concrete '#{item}' value for selected runtime-backed profiles."
    end
  end

  commands = runtime.section("## Commands")
  [
    "Install development dependencies",
    "Run in place",
    "Test",
    "Lint/static analysis",
    "Format check",
    "Build/package"
  ].each do |item|
    unless ValuePolicy.resolved?(runtime.table_value(item, section: commands))
      errors << "RUNTIME.md requires a resolved '#{item}' command for selected runtime-backed profiles."
    end
  end

  distribution = runtime.section("## Distribution")
  ["Skill distribution", "Version source of truth"].each do |item|
    unless ValuePolicy.resolved?(runtime.table_value(item, section: distribution))
      errors << "RUNTIME.md requires a concrete '#{item}' value for selected runtime-backed profiles."
    end
  end

  environment = runtime.section("## Environment and configuration")
  if environment.nil? || /\bTODO\b/i.match?(environment)
    errors << "RUNTIME.md must replace the environment/configuration placeholder with concrete variables or an explicit NONE record."
  end

  rationale = runtime.section("## Decision rationale")
  if rationale.nil? || rationale.strip.empty? || /\bTODO\b/i.match?(rationale)
    errors << "RUNTIME.md requires a concrete decision rationale for selected runtime-backed profiles."
  end

  if selection.selected?("packaged-cli")
    unless ValuePolicy.concrete?(runtime.table_value("Human CLI", section: commands))
      errors << "Selected profile 'packaged-cli' requires a concrete 'Human CLI' command in RUNTIME.md."
    end
    unless ValuePolicy.resolved?(runtime.table_value("CLI distribution", section: distribution))
      errors << "Selected profile 'packaged-cli' requires a resolved 'CLI distribution' value in RUNTIME.md."
    end
  end

  if selection.selected?("browser-interface")
    [
      "Start human verification Web UI",
      "Stop human verification Web UI",
      "Check human verification Web UI readiness"
    ].each do |item|
      unless ValuePolicy.concrete?(runtime.table_value(item, section: commands))
        errors << "Selected profile 'browser-interface' requires a concrete '#{item}' command in RUNTIME.md."
      end
    end

    web_deployment = runtime.section("## Optional human verification Web interface deployment")
    [
      "Supported",
      "Web runtime or entry point",
      "Deployment selection time",
      "Supported topologies",
      "Default topology",
      "Shared-listener support",
      "Separate-listener support",
      "External-origin model",
      "Browser-visible MCP exposure capability",
      "Enablement configuration"
    ].each do |item|
      unless ValuePolicy.resolved?(runtime.table_value(item, section: web_deployment))
        errors << "Selected profile 'browser-interface' requires a concrete '#{item}' value in the RUNTIME.md Web deployment section."
      end
    end
    unless runtime.table_value("Supported", section: web_deployment) == "YES"
      errors << "Selected profile 'browser-interface' requires 'Supported: YES' in the RUNTIME.md Web deployment section."
    end
    unless ValuePolicy.resolved?(runtime.table_value("Human Web interface distribution", section: distribution))
      errors << "Selected profile 'browser-interface' requires a resolved Web distribution value in RUNTIME.md."
    end
  end

  if selection.selected?("headless-service")
    [
      "Start headless service",
      "Stop headless service",
      "Check headless service readiness"
    ].each do |item|
      unless ValuePolicy.concrete?(runtime.table_value(item, section: commands))
        errors << "Selected profile 'headless-service' requires a concrete '#{item}' command in RUNTIME.md."
      end
    end

    service = runtime.section("## Headless service deployment")
    [
      "Supported",
      "Service runtime or entry point",
      "Protocol or API surface",
      "Endpoint or listener model",
      "Default bind address",
      "Port policy",
      "Authentication",
      "Authorization",
      "Exposure and non-loopback policy",
      "Request size and rate limits",
      "Concurrent request policy",
      "State or session model",
      "Readiness check",
      "Liveness check",
      "Timeout and cancellation policy",
      "Graceful shutdown and restart policy",
      "Deployment topology",
      "Security and deployment smoke tests"
    ].each do |item|
      unless ValuePolicy.resolved?(runtime.table_value(item, section: service))
        errors << "Selected profile 'headless-service' requires a concrete '#{item}' value in the RUNTIME.md service section."
      end
    end
    unless runtime.table_value("Supported", section: service) == "YES"
      errors << "Selected profile 'headless-service' requires 'Supported: YES' in the RUNTIME.md service section."
    end
    unless ValuePolicy.resolved?(runtime.table_value("Service integration", section: distribution))
      errors << "Selected profile 'headless-service' requires a resolved 'Service integration' value in RUNTIME.md."
    end
  end

  if selection.selected?("mcp-enabled")
    mcp_protocol = runtime.section("## MCP protocol support")
    [
      "Supported protocol revisions",
      "Supported protocol eras",
      "Default revision or negotiation mode",
      "MCP SDK or protocol library",
      "SDK version",
      "Legacy compatibility policy",
      "JSON Schema dialects",
      "Optional MCP extensions",
      "Deprecated feature policy",
      "Negotiation and compatibility tests"
    ].each do |item|
      unless ValuePolicy.resolved?(runtime.table_value(item, section: mcp_protocol))
        errors << "Selected profile 'mcp-enabled' requires a concrete '#{item}' value in RUNTIME.md."
      end
    end

    variant_sections = {
      "stdio" => runtime.section("### stdio variant"),
      "Streamable HTTP" => runtime.section("### Streamable HTTP variant"),
      "bundled client" => runtime.section("### Bundled ad hoc MCP tool client")
    }
    variant_support = {}
    variant_sections.each do |variant, content|
      support = runtime.table_value("Supported", section: content)
      variant_support[variant] = support
      unless %w[YES NO].include?(support)
        errors << "Selected profile 'mcp-enabled' requires '#{variant}' Supported to be YES or NO in RUNTIME.md."
      end
      if content.nil? || /\bTODO\b/i.match?(content)
        errors << "Selected profile 'mcp-enabled' must resolve all retained '#{variant}' RUNTIME.md fields using concrete or NOT SUPPORTED values."
      end
    end
    unless variant_support.values_at("stdio", "Streamable HTTP").include?("YES")
      errors << "Selected profile 'mcp-enabled' requires at least one supported MCP server transport in RUNTIME.md."
    end
    unless ValuePolicy.resolved?(runtime.table_value("MCP distribution", section: distribution))
      errors << "Selected profile 'mcp-enabled' requires a resolved 'MCP distribution' value in RUNTIME.md."
    end
  end
end

routing = repository.document("INTERFACES.md")
if (selected_profiles & %w[packaged-cli mcp-enabled]).any? && routing
  preferred_interface = routing.field("Preferred agent interface")
  unless ValuePolicy.resolved?(preferred_interface)
    errors << "Selected CLI or MCP profiles require a concrete 'Preferred agent interface:' in INTERFACES.md."
  end
end

if selection.selected?("packaged-cli")
  cli = repository.document("CLI_INTERFACE.md")
  if cli
    human_cli = cli.section("## Human CLI")
    if human_cli.nil?
      errors << "Selected profile 'packaged-cli' requires a '## Human CLI' contract in CLI_INTERFACE.md."
    else
      {
        "Command" => "canonical command",
        "Working directory" => "working directory",
        "Format" => "structured output format",
        "Contract version field" => "structured output contract version"
      }.each do |label, description_text|
        unless ValuePolicy.concrete?(cli.field(label, section: human_cli))
          errors << "Selected profile 'packaged-cli' requires a concrete #{description_text} in CLI_INTERFACE.md."
        end
      end
    end
  end
end

if selection.selected?("mcp-enabled")
  mcp = repository.document("MCP_INTERFACE.md")
  if mcp
    protocol_reference = mcp.section("## MCP protocol reference")
    if protocol_reference.nil?
      errors << "Selected profile 'mcp-enabled' requires an MCP protocol reference contract in MCP_INTERFACE.md."
    else
      ["Public negotiation and fallback behavior", "Public compatibility statement"].each do |label|
        unless ValuePolicy.resolved?(mcp.field(label, section: protocol_reference))
          errors << "Selected profile 'mcp-enabled' requires a concrete '#{label}:' value in MCP_INTERFACE.md."
        end
      end
    end

    support_values = mcp.support_values
    if support_values.empty? || support_values.none? { |value| ProfileContracts.support_token(value) == "YES" }
      errors << "Selected profile 'mcp-enabled' requires at least one MCP interface with 'Supported: YES' in MCP_INTERFACE.md."
    end
    if support_values.any? { |value| /\bUNSELECTED\b/i.match?(value) }
      errors << "Selected profile 'mcp-enabled' must resolve every retained MCP 'Supported:' field in MCP_INTERFACE.md."
    end
  end
end

if selection.selected?("browser-interface")
  web = repository.document("WEB_INTERFACE.md")
  if web
    if /\b(?:TODO|UNSELECTED)\b/i.match?(web.text)
      errors << "Selected profile 'browser-interface' must resolve every TODO and UNSELECTED value in WEB_INTERFACE.md."
    end
    unless web.field("Supported") == "YES"
      errors << "Selected profile 'browser-interface' requires 'Supported: YES' in WEB_INTERFACE.md."
    end
    ["Purpose", "Default enablement", "Production policy"].each do |label|
      unless ValuePolicy.resolved?(web.field(label))
        errors << "Selected profile 'browser-interface' requires a concrete '#{label}:' value in WEB_INTERFACE.md."
      end
    end

    [
      "External base URL",
      "Web UI path or URL",
      "MCP endpoint visible to the browser",
      "MCP endpoint used by the UI backend",
      "Authentication",
      "Allowed users or network boundary",
      "Read-only operations",
      "Mutating operations",
      "Destructive operations",
      "Confirmation policy",
      "Sensitive argument masking",
      "Sensitive result masking",
      "Audit logging",
      "Web health behavior",
      "Failure relationship"
    ].each do |label|
      unless ValuePolicy.resolved?(web.field(label))
        errors << "Selected profile 'browser-interface' requires a concrete '#{label}:' value in WEB_INTERFACE.md."
      end
    end

    relationship = web.section("## Relationship to MCP")
    interaction_values = [
      "backend acts as an MCP client",
      "browser calls MCP directly",
      "UI uses a non-MCP application API",
      "mixed model"
    ].map { |label| web.list_field(label, section: relationship) || web.field(label, section: relationship) }
    unless interaction_values.any? { |value| value == "YES" || (ValuePolicy.resolved?(value) && value != "NO") }
      errors << "Selected profile 'browser-interface' requires one concrete UI interaction model in WEB_INTERFACE.md."
    end

    capabilities = web.section("## UI capabilities")
    if capabilities.nil? || /\b(?:TODO|UNSELECTED)\b/i.match?(capabilities)
      errors << "Selected profile 'browser-interface' must resolve every UI capability field in WEB_INTERFACE.md."
    end

    required_tests = web.section("## Required tests")
    if required_tests.nil? || required_tests.strip.empty?
      errors << "Selected profile 'browser-interface' requires a non-empty Required tests section in WEB_INTERFACE.md."
    end

    rationale = web.section("## Decision rationale")
    if rationale.nil? || rationale.strip.empty? || /\bTODO\b/i.match?(rationale)
      errors << "Selected profile 'browser-interface' requires a concrete decision rationale in WEB_INTERFACE.md."
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Core Agent Skill profile contracts are valid."
