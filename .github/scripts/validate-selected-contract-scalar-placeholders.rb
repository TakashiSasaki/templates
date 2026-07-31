#!/usr/bin/env ruby
# frozen_string_literal: true

SKILL_PATH = "SKILL.md"
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

unresolved_scalar = lambda do |value|
  normalized = strip_backticks.call(value).gsub(/\s+/, " ").strip
  next false if normalized.empty?

  marker = /\A(?:TBD|FIXME|PLACEHOLDER)\.?\z/i
  phrase = /\A(?:(?:details?|behavior|contract|implementation|documentation)\s+(?:forthcoming|pending|to\s+follow)|to\s+be\s+(?:added|decided|determined|defined|documented|specified)|will\s+be\s+(?:added|defined|documented|specified)(?:\s+later)?)\.?\z/i
  marker.match?(normalized) || phrase.match?(normalized)
end

summary_values = lambda do |lines, label|
  lines.filter_map do |raw_line|
    normalized = raw_line.strip
    normalized = normalized[2..].strip if normalized.start_with?("- ")
    match = normalized.match(/\A#{Regexp.escape(label)}:\s*(.*?)\s*\z/)
    strip_backticks.call(match[1]) if match
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

errors = []

scan_scalar_values = lambda do |path, document, context = nil|
  document.lines.each_with_index do |raw_line, index|
    line_number = index + 1
    normalized = raw_line.strip
    next if normalized.empty? || normalized.match?(/\A```/)

    location = context ? "#{path} #{context}" : "#{path}:#{line_number}"

    if unresolved_scalar.call(normalized)
      errors << "#{location} must not contain standalone unresolved scalar placeholder " \
                "#{strip_backticks.call(normalized).inspect}."
    end

    field_match = normalized.match(/\A(?:[-*]\s+)?([^|#`][^:]{0,120}?):\s*(.*?)\s*\z/)
    if field_match
      label = field_match[1].strip
      value = field_match[2]
      if unresolved_scalar.call(value)
        errors << "#{location} '#{label}:' must not use unresolved scalar placeholder " \
                  "#{strip_backticks.call(value).inspect}."
      end
    end

    next unless normalized.start_with?("|") && normalized.end_with?("|")

    cells = normalized.split("|", -1)[1...-1].map(&:strip)
    next if cells.empty?
    next if cells.all? { |cell| /\A:?-+:?\z/.match?(cell) }

    cells.each_with_index do |cell, cell_index|
      next if cell_index.zero?
      next unless unresolved_scalar.call(cell)

      errors << "#{location} table value must not use unresolved scalar placeholder " \
                "#{strip_backticks.call(cell).inspect}."
    end
  end
end

skill_lines = File.readlines(SKILL_PATH, chomp: true)
profile_values = summary_values.call(skill_lines, "Selected profiles")
if profile_values.length != 1
  warn "#{SKILL_PATH} must contain exactly one 'Selected profiles:' declaration."
  exit 1
end

selected_profiles = profile_values.first.split(",").map(&:strip).reject(&:empty?)
if selected_profiles == ["template-scaffold"]
  puts "Selected-contract scalar placeholder validation is not activated for the template scaffold."
  exit 0
end

if (selected_profiles & %w[packaged-cli mcp-enabled]).any?
  [
    "Canonical command",
    "Working directory",
    "Preferred agent route",
    "Detailed interface contract"
  ].each do |label|
    summary_values.call(skill_lines, label).each do |value|
      if unresolved_scalar.call(value)
        errors << "#{SKILL_PATH} '#{label}:' must not use unresolved scalar placeholder #{value.inspect}."
      end
    end
  end
end

selected_contracts = []
selected_contracts << "CLI_INTERFACE.md" if selected_profiles.include?("packaged-cli")
selected_contracts << "MCP_INTERFACE.md" if selected_profiles.include?("mcp-enabled")

selected_contracts.each do |path|
  unless File.file?(path)
    errors << "Selected profile requires contract file: #{path}"
    next
  end

  scan_scalar_values.call(path, File.read(path))
end

if (selected_profiles & %w[packaged-cli mcp-enabled]).any?
  unless File.file?(RUNTIME_PATH)
    errors << "Selected public-interface profile requires contract file: #{RUNTIME_PATH}"
  else
    runtime = File.read(RUNTIME_PATH)
    runtime_headings = [
      "## Status",
      "## Primary implementation",
      "### Shared development commands",
      "## Distribution",
      "## Environment and configuration",
      "## Decision rationale"
    ]
    runtime_headings << "### Packaged CLI commands" if selected_profiles.include?("packaged-cli")
    if selected_profiles.include?("mcp-enabled")
      runtime_headings.concat([
        "### MCP commands",
        "## MCP protocol support",
        "### stdio variant",
        "### Streamable HTTP variant",
        "### Bundled ad hoc MCP tool client"
      ])
    end

    runtime_headings.each do |heading|
      section = markdown_section.call(runtime, heading)
      scan_scalar_values.call(RUNTIME_PATH, section, heading) if section
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Selected public-interface and runtime scalar values contain no unresolved placeholders."
