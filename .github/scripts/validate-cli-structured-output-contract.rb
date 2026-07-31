#!/usr/bin/env ruby
# frozen_string_literal: true

SKILL_PATH = "SKILL.md"
CLI_PATH = "CLI_INTERFACE.md"

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

field_value = lambda do |section, label|
  match = section&.match(/^#{Regexp.escape(label)}:\s*(.*?)\s*$/)
  match && strip_backticks.call(match[1])
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
if selected_profiles == ["template-scaffold"] || !selected_profiles.include?("packaged-cli")
  puts "CLI structured-output contract is not activated."
  exit 0
end

errors = []

unless File.file?(CLI_PATH)
  errors << "Selected profile 'packaged-cli' requires contract file: #{CLI_PATH}"
else
  cli = File.read(CLI_PATH)
  structured = markdown_section.call(cli, "### Structured output")

  if structured.nil? || structured.strip.empty?
    errors << "#{CLI_PATH} requires a non-empty '### Structured output' section."
  else
    mode_selector = field_value.call(structured, "Mode selector")
    format = field_value.call(structured, "Format")
    version_field = field_value.call(structured, "Contract version field")

    unresolved_selector = /\A(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE)|TODO|TBD|FIXME|PLACEHOLDER|UNSELECTED|PENDING|AUTOMATIC|DEFAULT|SEE\s+DOCUMENTATION)\z/i
    unresolved_selector_payload = /(?:\A|[:=]|\s)(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE)|TODO|TBD|FIXME|PLACEHOLDER|UNSELECTED|PENDING|AUTOMATIC|DEFAULT|SEE\s+DOCUMENTATION)(?=\z|[\s.,;])/i
    option_selector = /(?:\A|\s)--?[A-Za-z0-9][A-Za-z0-9_-]*(?:[=\s]\S+)?(?:\s|\z)/
    environment_selector = /(?:\A|\s)[A-Z][A-Z0-9_]*=\S+(?:\s|\z)/
    named_selector = /\A(?:subcommand|command|option|flag)\s*:\s*\S(?:.*\S)?\z/i
    selector_is_explicit = mode_selector && (
      option_selector.match?(mode_selector) ||
      environment_selector.match?(mode_selector) ||
      named_selector.match?(mode_selector)
    )
    selector_is_resolved = mode_selector &&
                           !unresolved_selector.match?(mode_selector) &&
                           !unresolved_selector_payload.match?(mode_selector)
    unless selector_is_explicit && selector_is_resolved
      errors << "#{CLI_PATH} 'Mode selector:' must record an exact, fully resolved caller-visible option, subcommand, or environment assignment that activates structured output."
    end

    # Format names are intentionally open-ended. A concrete skill may select a
    # standard or application-specific serialization without waiting for this
    # template's validator to add it to a whitelist. Reject only declarations
    # that explicitly deny structured machine readability, generic nonchoices,
    # placeholders, or prose too vague to identify a serialization contract.
    negative_format = /\b(?:PLAIN\s+TEXT|HUMAN[-\s]+READABLE|TEXT\s+ONLY|NO\s+STRUCTURED|UNSTRUCTURED|NOT\s+MACHINE[-\s]+READABLE)\b/i
    generic_format = /\A(?:TEXT|BINARY|CUSTOM|OTHER|UNKNOWN|NONE|NOT\s+(?:SUPPORTED|APPLICABLE)|TODO|TBD|UNSELECTED)\z/i
    format_name = /\A(?=.{1,80}\z)(?:[A-Za-z0-9][A-Za-z0-9._+\/-]*)(?:[ -][A-Za-z0-9][A-Za-z0-9._+\/-]*){0,5}\z/
    unless format && format_name.match?(format) && !negative_format.match?(format) && !generic_format.match?(format)
      errors << "#{CLI_PATH} 'Format:' must name an explicit machine-readable structured serialization format."
    end

    negative_version = /\A(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE)|NO\s+VERSION\s+FIELD)\z|\b(?:WITHOUT|OMITTED|ABSENT)\b/i
    field_selector = /\A(?:[A-Za-z_$][A-Za-z0-9_$-]*(?:\.[A-Za-z_$][A-Za-z0-9_$-]*)*|\/(?:[^\/\s]+\/)*[^\/\s]+)\z/
    unless version_field && !negative_version.match?(version_field) && field_selector.match?(version_field)
      errors << "#{CLI_PATH} 'Contract version field:' must name one concrete field or field path."
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "CLI structured-output contract is valid."
