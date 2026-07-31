#!/usr/bin/env ruby
# frozen_string_literal: true

SKILL_PATH = "SKILL.md"
MCP_PATH = "MCP_INTERFACE.md"
RUNTIME_PATH = "RUNTIME.md"

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

resolved_value = lambda do |value|
  value && !value.strip.empty? && !/\b(?:TODO|UNSELECTED)\b/i.match?(value)
end

concrete_value = lambda do |value|
  resolved_value.call(value) && !/\A(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE))\z/i.match?(value.strip)
end

runtime_reference = lambda do |value|
  /\Asee\s+RUNTIME\.md\z/i.match?(value.to_s.strip)
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

table_value = lambda do |section, item|
  match = section&.match(/^\|\s*#{Regexp.escape(item)}\s*\|\s*(.*?)\s*\|\s*$/)
  match && strip_backticks.call(match[1])
end

support_token = lambda do |value|
  value&.strip&.split(/[;\s]/)&.first&.upcase
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
  puts "Bundled MCP client consistency validation is not activated."
  exit 0
end

errors = []

unless File.file?(MCP_PATH)
  errors << "Selected profile 'mcp-enabled' requires #{MCP_PATH}."
end
unless File.file?(RUNTIME_PATH)
  errors << "Selected profile 'mcp-enabled' requires #{RUNTIME_PATH}."
end

if File.file?(MCP_PATH) && File.file?(RUNTIME_PATH)
  mcp = File.read(MCP_PATH)
  runtime = File.read(RUNTIME_PATH)
  public_client = markdown_section.call(mcp, "## Bundled ad hoc MCP tool client")
  runtime_client = markdown_section.call(runtime, "### Bundled ad hoc MCP tool client")

  public_support = support_token.call(field_value.call(public_client, "Supported"))
  runtime_support = support_token.call(table_value.call(runtime_client, "Supported"))

  unless %w[YES NO].include?(runtime_support)
    errors << "Bundled MCP client requires a resolved YES/NO support declaration in #{RUNTIME_PATH}."
  end

  if %w[YES NO].include?(public_support) && %w[YES NO].include?(runtime_support) &&
     public_support != runtime_support
    errors << "Bundled MCP client support must agree between #{MCP_PATH} and #{RUNTIME_PATH}."
  end

  if public_support == "YES"
    selection_pairs = [
      ["Scope", "Scope", false],
      ["Negotiation and compatibility behavior", "Negotiation and compatibility behavior", false],
      ["Invocation scope", "Invocation scope", false],
      ["Interaction modes", "Interaction modes", false],
      ["Task or extension support", "Task or extension support", true]
    ]

    selection_pairs.each do |public_label, runtime_item, allow_not_supported|
      public_value = field_value.call(public_client, public_label)
      runtime_value = table_value.call(runtime_client, runtime_item)
      public_valid = concrete_value.call(public_value) ||
                     (allow_not_supported && /\ANOT\s+SUPPORTED\z/i.match?(public_value.to_s.strip))
      runtime_valid = concrete_value.call(runtime_value) ||
                      (allow_not_supported && /\ANOT\s+SUPPORTED\z/i.match?(runtime_value.to_s.strip))

      unless public_valid
        errors << "Bundled MCP client #{public_label} requires a concrete caller-visible value" \
                  "#{allow_not_supported ? ", 'NOT SUPPORTED'," : ""} or 'see RUNTIME.md'."
        next
      end
      unless runtime_valid
        errors << "Bundled MCP client #{public_label} requires a concrete authoritative value" \
                  "#{allow_not_supported ? " or 'NOT SUPPORTED'" : ""} in #{RUNTIME_PATH}."
        next
      end
      next if runtime_reference.call(public_value) || public_value == runtime_value

      errors << "Bundled MCP client #{public_label} must match #{RUNTIME_PATH} exactly or explicitly say " \
                "'see RUNTIME.md': #{public_value.inspect} != #{runtime_value.inspect}."
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Bundled MCP client public and runtime selections are consistent."
