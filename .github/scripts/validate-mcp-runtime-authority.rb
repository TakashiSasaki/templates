#!/usr/bin/env ruby
# frozen_string_literal: true

SKILL_PATH = "SKILL.md"
MCP_PATH = "MCP_INTERFACE.md"
AUTHORITY_LABEL = "Runtime, SDK, revision, era boundary, and schema source of truth"

unless File.file?(SKILL_PATH)
  warn "Missing universally required file: #{SKILL_PATH}"
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

field_values = lambda do |section, label|
  section.to_s.scan(/^#{Regexp.escape(label)}:\s*(.*?)\s*$/).flatten.map do |value|
    strip_backticks.call(value)
  end
end

profile_values = File.readlines(SKILL_PATH, chomp: true).filter_map do |raw_line|
  normalized = raw_line.strip
  normalized = normalized[2..].strip if normalized.start_with?("- ")
  match = normalized.match(/\ASelected profiles:\s*(.+?)\s*\z/)
  strip_backticks.call(match[1]) if match
end

if profile_values.length != 1
  warn "#{SKILL_PATH} must contain exactly one 'Selected profiles:' declaration."
  exit 1
end

selected_profiles = profile_values.first.split(",").map(&:strip).reject(&:empty?)
if selected_profiles == ["template-scaffold"] || !selected_profiles.include?("mcp-enabled")
  puts "MCP runtime-authority declaration is not activated."
  exit 0
end

errors = []

unless File.file?(MCP_PATH)
  errors << "Selected profile 'mcp-enabled' requires contract file: #{MCP_PATH}"
else
  mcp = File.read(MCP_PATH)
  protocol = markdown_section.call(mcp, "## MCP protocol reference")
  values = field_values.call(protocol, AUTHORITY_LABEL)

  if values.length != 1
    errors << "#{MCP_PATH} must contain exactly one '#{AUTHORITY_LABEL}:' declaration under '## MCP protocol reference'."
  elsif values.first != "RUNTIME.md"
    errors << "#{MCP_PATH} '#{AUTHORITY_LABEL}:' must resolve exactly to RUNTIME.md."
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "MCP runtime-authority declaration is valid."
