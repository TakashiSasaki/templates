#!/usr/bin/env ruby

require "find"
require "open3"
require "yaml"

skill_path = "SKILL.md"
lines = File.readlines(skill_path, chomp: true)
skill_text = lines.join("\n")

closing_index = (1...lines.length).find { |index| lines[index] == "---" }
frontmatter = lines[1...closing_index].join("\n")
metadata = YAML.safe_load(
  frontmatter,
  permitted_classes: [],
  permitted_symbols: [],
  aliases: false
)
name = metadata.fetch("name")
description = metadata.fetch("description")

normalize_line = lambda do |line|
  normalized = line.strip
  normalized = normalized[2..].strip if normalized.start_with?("- ")
  normalized
end

strip_backticks = lambda do |value|
  normalized = value.strip
  if normalized.length >= 2 && normalized.start_with?("`") && normalized.end_with?("`")
    normalized[1...-1]
  else
    normalized
  end
end

markdown_section = lambda do |text, heading|
  level = heading[/\A#+/].length
  boundary = level == 2 ? "^##\\s|\\z" : "^(?:##|###)\\s|\\z"
  pattern = Regexp.new(
    "^#{Regexp.escape(heading)}\\s*$\\n(.*?)(?=#{boundary})",
    Regexp::MULTILINE
  )
  match = text.match(pattern)
  match && match[1]
end

field_value = lambda do |text, label|
  match = text&.match(/^#{Regexp.escape(label)}:\s*(.*?)\s*$/)
  match && match[1].strip
end

table_value = lambda do |text, item|
  match = text&.match(/^\|\s*#{Regexp.escape(item)}\s*\|\s*(.*?)\s*\|\s*$/)
  match && match[1].strip
end

resolved_value = lambda do |value|
  value && !value.empty? && !/\b(?:UNSELECTED|TODO)\b/i.match?(value)
end

concrete_value = lambda do |value|
  resolved_value.call(value) && !/\bNOT\s+(?:SUPPORTED|APPLICABLE)\b/i.match?(value)
end

profile_declarations = []

lines.each_with_index do |raw_line, index|
  line = normalize_line.call(raw_line)
  next unless (match = line.match(/\ASelected profiles:\s*(.+?)\s*\z/))

  profile_declarations << {
    value: strip_backticks.call(match[1]),
    line: index + 1
  }
end

if profile_declarations.length != 1
  warn "SKILL.md must contain exactly one 'Selected profiles:' declaration."
  exit 1
end

selected_profiles = profile_declarations.first[:value].split(",").map(&:strip).reject(&:empty?)
allowed_profiles = %w[
  instruction-only
  knowledge-augmented
  asset-driven
  script-assisted
  packaged-cli
  mcp-enabled
  browser-interface
  headless-service
]

template_scaffold = selected_profiles == ["template-scaffold"]

if template_scaffold
  unless name == "agent-skill-template"
    warn "'template-scaffold' is valid only for the uncustomized agent-skill-template."
    exit 1
  end
elsif selected_profiles.include?("template-scaffold")
  warn "'template-scaffold' cannot be combined with concrete skill profiles."
  exit 1
end

if selected_profiles.empty?
  warn "SKILL.md must select at least one concrete profile."
  exit 1
end

unless template_scaffold
  duplicates = selected_profiles.group_by(&:itself).select { |_profile, values| values.length > 1 }.keys
  unless duplicates.empty?
    warn "SKILL.md contains duplicate selected profiles: #{duplicates.join(', ')}"
    exit 1
  end

  invalid_profiles = selected_profiles - allowed_profiles
  unless invalid_profiles.empty?
    warn "SKILL.md contains unknown selected profiles: #{invalid_profiles.join(', ')}"
    exit 1
  end
end

profile_requirements = {
  "packaged-cli" => ["RUNTIME.md", "INTERFACES.md"],
  "mcp-enabled" => ["RUNTIME.md", "INTERFACES.md", "docs/mcp-transports.md"],
  "browser-interface" => ["RUNTIME.md", "WEB_INTERFACE.md"],
  "headless-service" => ["RUNTIME.md"]
}

resource_profile_requirements = {
  "references" => "knowledge-augmented",
  "assets" => "asset-driven",
  "scripts" => "script-assisted",
  "mcp" => "mcp-enabled"
}

operational_files_present = lambda do |directory|
  next false unless Dir.exist?(directory) && !File.symlink?(directory)

  found = false
  Find.find(directory) do |path|
    next if path == directory
    next if File.directory?(path)
    next if path == "#{directory}/README.md"

    found = true
    break
  end
  found
end

errors = []

if template_scaffold
  customized_directories = resource_profile_requirements.keys.select do |directory|
    operational_files_present.call(directory)
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

  if /\bTODO\b/i.match?(skill_text)
    errors << "A concrete SKILL.md must not retain TODO placeholders."
  end

  required_skill_sections = [
    "## Purpose",
    "## Use this skill when",
    "## Workflow",
    "## Output requirements",
    "## Validation",
    "## Safety and approval"
  ]
  required_skill_sections.each do |heading|
    content = markdown_section.call(skill_text, heading)
    if content.nil? || content.strip.empty?
      errors << "A concrete SKILL.md requires non-empty content under '#{heading}'."
    end
  end

  selected_profiles.each do |profile|
    profile_requirements.fetch(profile, []).each do |required_path|
      unless File.file?(required_path)
        errors << "Selected profile '#{profile}' requires contract file: #{required_path}"
      end
    end
  end

  resource_profile_requirements.each do |directory, required_profile|
    next unless operational_files_present.call(directory)
    next if selected_profiles.include?(required_profile)

    errors << "Retained operational files under #{directory}/ require selected profile '#{required_profile}'."
  end

  supported_contracts = {
    "RUNTIME.md" => %w[script-assisted packaged-cli mcp-enabled browser-interface headless-service],
    "INTERFACES.md" => %w[packaged-cli mcp-enabled],
    "WEB_INTERFACE.md" => %w[browser-interface]
  }
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

if runtime_selected && File.file?("RUNTIME.md")
  runtime = File.read("RUNTIME.md")
  runtime_status = field_value.call(runtime, "Selection status")
  unless runtime_status == "SELECTED"
    errors << "Selected runtime-backed profiles require 'Selection status: SELECTED' in RUNTIME.md."
  end

  primary = markdown_section.call(runtime, "## Primary implementation")
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
    unless resolved_value.call(table_value.call(primary, item))
      errors << "RUNTIME.md requires a concrete '#{item}' value for selected runtime-backed profiles."
    end
  end

  commands = markdown_section.call(runtime, "## Commands")
  [
    "Install development dependencies",
    "Run in place",
    "Test",
    "Lint/static analysis",
    "Format check",
    "Build/package"
  ].each do |item|
    unless resolved_value.call(table_value.call(commands, item))
      errors << "RUNTIME.md requires a resolved '#{item}' command for selected runtime-backed profiles."
    end
  end

  distribution = markdown_section.call(runtime, "## Distribution")
  ["Skill distribution", "Version source of truth"].each do |item|
    unless resolved_value.call(table_value.call(distribution, item))
      errors << "RUNTIME.md requires a concrete '#{item}' value for selected runtime-backed profiles."
    end
  end

  environment = markdown_section.call(runtime, "## Environment and configuration")
  if environment.nil? || /\bTODO\b/i.match?(environment)
    errors << "RUNTIME.md must replace the environment/configuration placeholder with concrete variables or an explicit NONE record."
  end

  rationale = markdown_section.call(runtime, "## Decision rationale")
  if rationale.nil? || rationale.strip.empty? || /\bTODO\b/i.match?(rationale)
    errors << "RUNTIME.md requires a concrete decision rationale for selected runtime-backed profiles."
  end

  if selected_profiles.include?("packaged-cli")
    unless concrete_value.call(table_value.call(commands, "Human CLI"))
      errors << "Selected profile 'packaged-cli' requires a concrete 'Human CLI' command in RUNTIME.md."
    end
    unless resolved_value.call(table_value.call(distribution, "CLI distribution"))
      errors << "Selected profile 'packaged-cli' requires a resolved 'CLI distribution' value in RUNTIME.md."
    end
  end

  if selected_profiles.include?("browser-interface")
    [
      "Start human verification Web UI",
      "Stop human verification Web UI",
      "Check human verification Web UI readiness"
    ].each do |item|
      unless concrete_value.call(table_value.call(commands, item))
        errors << "Selected profile 'browser-interface' requires a concrete '#{item}' command in RUNTIME.md."
      end
    end

    web_deployment = markdown_section.call(runtime, "## Optional human verification Web interface deployment")
    web_items = [
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
    ]
    web_items.each do |item|
      unless resolved_value.call(table_value.call(web_deployment, item))
        errors << "Selected profile 'browser-interface' requires a concrete '#{item}' value in the RUNTIME.md Web deployment section."
      end
    end
    unless table_value.call(web_deployment, "Supported") == "YES"
      errors << "Selected profile 'browser-interface' requires 'Supported: YES' in the RUNTIME.md Web deployment section."
    end
    unless resolved_value.call(table_value.call(distribution, "Human Web interface distribution"))
      errors << "Selected profile 'browser-interface' requires a resolved Web distribution value in RUNTIME.md."
    end
  end

  if selected_profiles.include?("headless-service")
    [
      "Start headless service",
      "Stop headless service",
      "Check headless service readiness"
    ].each do |item|
      unless concrete_value.call(table_value.call(commands, item))
        errors << "Selected profile 'headless-service' requires a concrete '#{item}' command in RUNTIME.md."
      end
    end

    service = markdown_section.call(runtime, "## Headless service deployment")
    service_items = [
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
    ]
    service_items.each do |item|
      unless resolved_value.call(table_value.call(service, item))
        errors << "Selected profile 'headless-service' requires a concrete '#{item}' value in the RUNTIME.md service section."
      end
    end
    unless table_value.call(service, "Supported") == "YES"
      errors << "Selected profile 'headless-service' requires 'Supported: YES' in the RUNTIME.md service section."
    end
    unless resolved_value.call(table_value.call(distribution, "Service integration"))
      errors << "Selected profile 'headless-service' requires a resolved 'Service integration' value in RUNTIME.md."
    end
  end

  if selected_profiles.include?("mcp-enabled")
    mcp_protocol = markdown_section.call(runtime, "## MCP protocol support")
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
      unless resolved_value.call(table_value.call(mcp_protocol, item))
        errors << "Selected profile 'mcp-enabled' requires a concrete '#{item}' value in RUNTIME.md."
      end
    end

    stdio = markdown_section.call(runtime, "### stdio variant")
    http = markdown_section.call(runtime, "### Streamable HTTP variant")
    bundled = markdown_section.call(runtime, "### Bundled ad hoc MCP tool client")
    variant_sections = {
      "stdio" => stdio,
      "Streamable HTTP" => http,
      "bundled client" => bundled
    }
    variant_support = {}
    variant_sections.each do |variant, content|
      support = table_value.call(content, "Supported")
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

    unless resolved_value.call(table_value.call(distribution, "MCP distribution"))
      errors << "Selected profile 'mcp-enabled' requires a resolved 'MCP distribution' value in RUNTIME.md."
    end
  end
end

interface_profiles = %w[packaged-cli mcp-enabled]
if (selected_profiles & interface_profiles).any? && File.file?("INTERFACES.md")
  interfaces = File.read("INTERFACES.md")
  preferred_interface = field_value.call(interfaces, "Preferred agent interface")
  unless resolved_value.call(preferred_interface)
    errors << "Selected CLI or MCP profiles require a concrete 'Preferred agent interface:' in INTERFACES.md."
  end

  if selected_profiles.include?("packaged-cli")
    human_cli = markdown_section.call(interfaces, "## Human CLI")
    if human_cli.nil?
      errors << "Selected profile 'packaged-cli' requires a '## Human CLI' contract in INTERFACES.md."
    else
      {
        "Command" => "canonical command",
        "Working directory" => "working directory",
        "Format" => "structured output format",
        "Contract version field" => "structured output contract version"
      }.each do |label, label_description|
        value = field_value.call(human_cli, label)
        unless concrete_value.call(value)
          errors << "Selected profile 'packaged-cli' requires a concrete #{label_description} in INTERFACES.md."
        end
      end
    end
  end

  if selected_profiles.include?("mcp-enabled")
    mcp_reference = markdown_section.call(interfaces, "## MCP protocol reference")
    if mcp_reference.nil?
      errors << "Selected profile 'mcp-enabled' requires an MCP protocol reference contract in INTERFACES.md."
    else
      ["Public negotiation and fallback behavior", "Public compatibility statement"].each do |label|
        unless resolved_value.call(field_value.call(mcp_reference, label))
          errors << "Selected profile 'mcp-enabled' requires a concrete '#{label}:' value in INTERFACES.md."
        end
      end
    end

    support_values = interfaces.scan(/^Supported:\s*(.*?)\s*$/).flatten.map(&:strip)
    if support_values.empty? || support_values.none? { |value| value == "YES" }
      errors << "Selected profile 'mcp-enabled' requires at least one MCP interface with 'Supported: YES' in INTERFACES.md."
    end
    if support_values.any? { |value| /\bUNSELECTED\b/i.match?(value) }
      errors << "Selected profile 'mcp-enabled' must resolve every retained MCP 'Supported:' field in INTERFACES.md."
    end
  end
end

if selected_profiles.include?("browser-interface") && File.file?("WEB_INTERFACE.md")
  web_interface = File.read("WEB_INTERFACE.md")
  unless field_value.call(web_interface, "Supported") == "YES"
    errors << "Selected profile 'browser-interface' requires 'Supported: YES' in WEB_INTERFACE.md."
  end
  ["Purpose", "Default enablement", "Production policy"].each do |label|
    unless resolved_value.call(field_value.call(web_interface, label))
      errors << "Selected profile 'browser-interface' requires a concrete '#{label}:' value in WEB_INTERFACE.md."
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end
