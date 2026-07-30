#!/usr/bin/env ruby

require "find"
require "open3"
require "yaml"

skill_path = "SKILL.md"
lines = File.readlines(skill_path, chomp: true)

closing_index = (1...lines.length).find { |index| lines[index] == "---" }
frontmatter = lines[1...closing_index].join("\n")
metadata = YAML.safe_load(
  frontmatter,
  permitted_classes: [],
  permitted_symbols: [],
  aliases: false
)
name = metadata.fetch("name")

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

if selected_profiles == ["template-scaffold"]
  unless name == "agent-skill-template"
    warn "'template-scaffold' is valid only for the uncustomized agent-skill-template."
    exit 1
  end
  exit 0
end

if selected_profiles.include?("template-scaffold")
  warn "'template-scaffold' cannot be combined with concrete skill profiles."
  exit 1
end

if selected_profiles.empty?
  warn "SKILL.md must select at least one concrete profile."
  exit 1
end

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

profile_requirements = {
  "packaged-cli" => ["RUNTIME.md", "INTERFACES.md"],
  "mcp-enabled" => ["RUNTIME.md", "INTERFACES.md", "docs/mcp-transports.md"],
  "browser-interface" => ["RUNTIME.md", "WEB_INTERFACE.md"]
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

field_value = lambda do |text, label|
  match = text.match(/^#{Regexp.escape(label)}:\s*(.*?)\s*$/)
  match && match[1].strip
end

resolved_value = lambda do |value|
  value && !value.empty? && !/\b(?:UNSELECTED|TODO)\b/i.match?(value)
end

section = lambda do |text, heading|
  level = heading[/\A#+/].length
  pattern = /^#{Regexp.escape(heading)}\s*$\n(.*?)(?=^#{1,#{level}}\s|\z)/m
  match = text.match(pattern)
  match && match[1]
end

errors = []

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

runtime_profiles = %w[packaged-cli mcp-enabled browser-interface]
if (selected_profiles & runtime_profiles).any? && File.file?("RUNTIME.md")
  runtime = File.read("RUNTIME.md")
  runtime_status = field_value.call(runtime, "Selection status")
  unless runtime_status == "SELECTED"
    errors << "Selected application profiles require 'Selection status: SELECTED' in RUNTIME.md."
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
    human_cli = section.call(interfaces, "## Human CLI")
    if human_cli.nil?
      errors << "Selected profile 'packaged-cli' requires a '## Human CLI' contract in INTERFACES.md."
    else
      {
        "Command" => "canonical command",
        "Working directory" => "working directory",
        "Format" => "structured output format",
        "Contract version field" => "structured output contract version"
      }.each do |label, description|
        value = field_value.call(human_cli, label)
        unless resolved_value.call(value) && !/\bNOT APPLICABLE\b/i.match?(value)
          errors << "Selected profile 'packaged-cli' requires a concrete #{description} in INTERFACES.md."
        end
      end
    end
  end

  if selected_profiles.include?("mcp-enabled")
    mcp_reference = section.call(interfaces, "## MCP protocol reference")
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
