#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "lib/profile_contracts"

SKILL_PATH = "SKILL.md"
ROUTING_PATH = "INTERFACES.md"
RUNTIME_PATH = "RUNTIME.md"
WEB_PATH = "WEB_INTERFACE.md"
RUNTIME_REQUIRED_PROFILES = %w[packaged-cli mcp-enabled browser-interface headless-service].freeze

begin
  selection = ProfileContracts::ProfileSelection.load(SKILL_PATH)
rescue ProfileContracts::ParseError => error
  warn error.message
  exit 1
end

if selection.template_scaffold?
  puts "Selected-contract scalar placeholder validation is not activated for the template scaffold."
  exit 0
end

policy = ProfileContracts::ValuePolicy
errors = []

scan_scalar_values = lambda do |path, document, context = nil|
  document.each_scalar do |entry|
    next unless policy.unresolved_scalar?(entry.value)

    location = context ? "#{path} #{context}" : "#{path}:#{entry.line_number}"
    value = policy.strip_backticks(entry.value)

    case entry.kind
    when :field
      errors << "#{location} '#{entry.label}:' must not use unresolved scalar placeholder #{value.inspect}."
    when :table
      errors << "#{location} table value must not use unresolved scalar placeholder #{value.inspect}."
    else
      errors << "#{location} must not contain standalone unresolved scalar placeholder #{value.inspect}."
    end
  end
end

skill_document = ProfileContracts::MarkdownDocument.read(SKILL_PATH)
selected_profiles = selection.profiles

# Every concrete skill must be operational regardless of whether it retains an
# implementation runtime. Scan the entire SKILL document so instruction-only,
# knowledge, asset, and script profiles cannot leave TBD-style placeholders in
# their purpose, trigger, workflow, output, validation, or safety sections.
scan_scalar_values.call(SKILL_PATH, skill_document)

routing_selected = (selected_profiles & %w[packaged-cli mcp-enabled]).any?
runtime_required = (selected_profiles & RUNTIME_REQUIRED_PROFILES).any?
runtime_retained = runtime_required || (selection.selected?("script-assisted") && File.file?(RUNTIME_PATH))

if runtime_retained
  ["Canonical command", "Working directory"].each do |label|
    skill_document.summary_values(label).each do |value|
      if policy.unresolved_scalar?(value)
        errors << "#{SKILL_PATH} '#{label}:' must not use unresolved scalar placeholder #{value.inspect}."
      end
    end
  end
end

if routing_selected
  ["Preferred agent route", "Detailed interface contract"].each do |label|
    skill_document.summary_values(label).each do |value|
      if policy.unresolved_scalar?(value)
        errors << "#{SKILL_PATH} '#{label}:' must not use unresolved scalar placeholder #{value.inspect}."
      end
    end
  end
end

selected_contracts = []
selected_contracts << ROUTING_PATH if routing_selected
selected_contracts << "CLI_INTERFACE.md" if selection.selected?("packaged-cli")
selected_contracts << "MCP_INTERFACE.md" if selection.selected?("mcp-enabled")
selected_contracts << WEB_PATH if selection.selected?("browser-interface")

selected_contracts.each do |path|
  unless File.file?(path)
    errors << "Selected profile requires contract file: #{path}"
    next
  end

  scan_scalar_values.call(path, ProfileContracts::MarkdownDocument.read(path))
end

if runtime_required && !File.file?(RUNTIME_PATH)
  errors << "Selected runtime-backed profile requires contract file: #{RUNTIME_PATH}"
elsif runtime_retained
  runtime = ProfileContracts::MarkdownDocument.read(RUNTIME_PATH)
  runtime_headings = [
    "## Status",
    "## Primary implementation",
    "### Shared development commands",
    "## Distribution",
    "## Environment and configuration",
    "## Decision rationale"
  ]
  runtime_headings << "### Packaged CLI commands" if selection.selected?("packaged-cli")
  if selection.selected?("mcp-enabled")
    runtime_headings.concat([
      "### MCP commands",
      "## MCP protocol support",
      "### stdio variant",
      "### Streamable HTTP variant",
      "### Bundled ad hoc MCP tool client"
    ])
  end
  if selection.selected?("browser-interface")
    runtime_headings.concat([
      "### Browser-interface commands",
      "## Optional human verification Web interface deployment"
    ])
  end
  if selection.selected?("headless-service")
    runtime_headings.concat([
      "### Headless-service commands",
      "## Headless service deployment"
    ])
  end

  runtime_headings.uniq.each do |heading|
    section = runtime.section(heading)
    next unless section

    scan_scalar_values.call(
      RUNTIME_PATH,
      ProfileContracts::MarkdownDocument.new(section, path: RUNTIME_PATH),
      heading
    )
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Concrete SKILL, selected routing/interface, and runtime scalar values contain no unresolved placeholders."
