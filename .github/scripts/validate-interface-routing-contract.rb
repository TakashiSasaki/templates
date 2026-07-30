#!/usr/bin/env ruby
# frozen_string_literal: true

SKILL_PATH = "SKILL.md"
ROUTING_PATH = "INTERFACES.md"
PUBLIC_INTERFACE_PROFILES = %w[packaged-cli mcp-enabled].freeze

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

resolved_value = lambda do |value|
  value && !value.strip.empty? && !/\b(?:TODO|UNSELECTED)\b/i.match?(value)
end

concrete_value = lambda do |value|
  resolved_value.call(value) && !/\A(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE))\z/i.match?(value.strip)
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
if selected_profiles == ["template-scaffold"]
  puts "Public interface routing contract is valid for the template scaffold."
  exit 0
end

routing_selected = (selected_profiles & PUBLIC_INTERFACE_PROFILES).any?
errors = []

if !routing_selected && File.exist?(ROUTING_PATH)
  errors << "Retained contract #{ROUTING_PATH} is unsupported without packaged-cli or mcp-enabled."
elsif routing_selected
  unless File.file?(ROUTING_PATH)
    errors << "Selected public-interface profiles require contract file: #{ROUTING_PATH}"
  else
    document = File.read(ROUTING_PATH)
    required_headings = [
      "## Status",
      "## Execution policy",
      "## Contract index",
      "## Cross-interface invariants",
      "## Availability and failure behavior",
      "## Decision rationale"
    ]

    required_headings.each do |heading|
      section = markdown_section.call(document, heading)
      if section.nil? || section.strip.empty?
        errors << "Selected routing contract #{ROUTING_PATH} requires non-empty section '#{heading}'."
      end
    end

    status = field_value.call(markdown_section.call(document, "## Status"), "Selection status")
    unless status == "SELECTED"
      errors << "Selected routing contract #{ROUTING_PATH} requires 'Selection status: SELECTED'."
    end

    if /\b(?:TODO|UNSELECTED)\b/i.match?(document)
      errors << "Selected routing contract #{ROUTING_PATH} must not retain TODO or UNSELECTED placeholders."
    end

    execution = markdown_section.call(document, "## Execution policy")
    unless concrete_value.call(field_value.call(execution, "Preferred agent interface"))
      errors << "#{ROUTING_PATH} requires a concrete 'Preferred agent interface:' value."
    end

    fallbacks = ["Fallback 1", "Fallback 2"].to_h do |label|
      [label, field_value.call(execution, label)]
    end
    fallbacks.each do |label, value|
      unless resolved_value.call(value)
        errors << "#{ROUTING_PATH} requires a resolved '#{label}:' value; use NONE when no route is permitted."
      end
    end
    if fallbacks["Fallback 1"]&.casecmp?("NONE") &&
       resolved_value.call(fallbacks["Fallback 2"]) &&
       !fallbacks["Fallback 2"].casecmp?("NONE")
      errors << "#{ROUTING_PATH} cannot define Fallback 2 after Fallback 1 is NONE."
    end

    availability = markdown_section.call(document, "## Availability and failure behavior")
    [
      "Unavailable preferred interface behavior",
      "Fallback activation conditions",
      "Failure classification exposed to callers"
    ].each do |label|
      unless concrete_value.call(field_value.call(availability, label))
        errors << "#{ROUTING_PATH} requires a concrete '#{label}:' value."
      end
    end

    rationale = markdown_section.call(document, "## Decision rationale")
    unless concrete_value.call(field_value.call(rationale, "Rationale"))
      errors << "#{ROUTING_PATH} requires a concrete 'Rationale:' value."
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Public interface routing contract is valid."
