#!/usr/bin/env ruby
# frozen_string_literal: true

SKILL_PATH = "SKILL.md"

unless File.file?(SKILL_PATH)
  warn "Missing universally required file: SKILL.md"
  exit 1
end

strip_backticks = lambda do |value|
  normalized = value.to_s.strip
  if normalized.length >= 2 && normalized.start_with?("`") && normalized.end_with?("`")
    normalized[1...-1]
  else
    normalized
  end
end

markdown_section = lambda do |document, heading|
  level = heading[/\A#+/].length
  boundary = level == 2 ? "^##\\s|\\z" : "^(?:##|###)\\s|\\z"
  match = document.match(
    Regexp.new("^#{Regexp.escape(heading)}\\s*$\\n(.*?)(?=#{boundary})", Regexp::MULTILINE)
  )
  match && match[1]
end

field_value = lambda do |section, label|
  match = section&.match(/^#{Regexp.escape(label)}:\s*(.*?)\s*$/)
  match && strip_backticks.call(match[1])
end

lines = File.readlines(SKILL_PATH, chomp: true)
profile_values = lines.filter_map do |raw_line|
  normalized = raw_line.strip
  normalized = normalized[2..].strip if normalized.start_with?("- ")
  match = normalized.match(/\ASelected profiles:\s*(.+?)\s*\z/)
  strip_backticks.call(match[1]) if match
end

if profile_values.length != 1
  warn "SKILL.md must contain exactly one 'Selected profiles:' declaration."
  exit 1
end

selected_profiles = profile_values.first.split(",").map(&:strip).reject(&:empty?)
exit 0 if selected_profiles == ["template-scaffold"]

contract_specs = {
  "packaged-cli" => {
    path: "CLI_INTERFACE.md",
    sections: [
      "## Status",
      "## Human CLI",
      "## Inputs, outputs, and side effects",
      "## Compatibility and versioning",
      "## Semantic-equivalence and test requirements",
      "## Decision rationale"
    ]
  },
  "mcp-enabled" => {
    path: "MCP_INTERFACE.md",
    sections: [
      "## Status",
      "## MCP protocol reference",
      "## stdio MCP server variant",
      "## Streamable HTTP MCP server variant",
      "## Bundled ad hoc MCP tool client",
      "## Semantic-equivalence and test requirements",
      "## Decision rationale"
    ]
  }
}

errors = []

contract_specs.each do |profile, spec|
  next unless selected_profiles.include?(profile)

  path = spec[:path]
  unless File.file?(path)
    errors << "Selected profile '#{profile}' requires contract file: #{path}"
    next
  end

  contract = File.read(path)
  status = field_value.call(markdown_section.call(contract, "## Status"), "Selection status")
  unless status == "SELECTED"
    errors << "Selected profile '#{profile}' requires 'Selection status: SELECTED' in #{path}."
  end

  if /\b(?:TODO|UNSELECTED)\b/i.match?(contract)
    errors << "Selected profile '#{profile}' must resolve every TODO and UNSELECTED value in #{path}."
  end

  spec[:sections].each do |heading|
    section = markdown_section.call(contract, heading)
    if section.nil? || section.strip.empty? || /\b(?:TODO|UNSELECTED)\b/i.match?(section)
      errors << "Selected profile '#{profile}' requires concrete content under '#{heading}' in #{path}."
    end
  end
end

{
  "CLI_INTERFACE.md" => ["packaged-cli"],
  "MCP_INTERFACE.md" => ["mcp-enabled"]
}.each do |path, profiles|
  next unless File.exist?(path)
  next unless (selected_profiles & profiles).empty?

  errors << "Retained contract #{path} is unsupported by the selected profiles."
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Decomposed public interface contracts are valid."
