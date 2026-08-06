#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "lib/profile_contracts"

SKILL_PATH = "SKILL.md"
CLI_PATH = "CLI_INTERFACE.md"

begin
  selection = ProfileContracts::ProfileSelection.load(SKILL_PATH)
rescue ProfileContracts::ParseError => error
  warn error.message
  exit 1
end

if selection.template_scaffold? || !selection.selected?("packaged-cli")
  puts "CLI structured-output contract is not activated."
  exit 0
end

errors = []

unless File.file?(CLI_PATH)
  errors << "Selected profile 'packaged-cli' requires contract file: #{CLI_PATH}"
else
  cli = ProfileContracts::MarkdownDocument.read(CLI_PATH)
  structured = cli.section("### Structured output")

  if structured.nil? || structured.strip.empty?
    errors << "#{CLI_PATH} requires a non-empty '### Structured output' section."
  else
    structured_document = ProfileContracts::MarkdownDocument.new(structured, path: CLI_PATH)
    mode_selector = structured_document.field("Mode selector")
    format = structured_document.field("Format")
    version_field = structured_document.field("Contract version field")

    unresolved_selector = /\A(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE)|TODO|TBD|FIXME|PLACEHOLDER|UNSELECTED|PENDING|AUTOMATIC|DEFAULT|SEE\s+DOCUMENTATION)\z/i
    unresolved_selector_payload = /(?:\A|[:=]|\s)(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE)|TODO|TBD|FIXME|PLACEHOLDER|UNSELECTED|PENDING|AUTOMATIC|DEFAULT|SEE\s+DOCUMENTATION)(?=\z|[\s.,;])/i
    option_selector = /(?:\A|\s)--?[A-Za-z0-9][A-Za-z0-9_-]*(?:[=\s]\S+)?(?:\s|\z)/
    environment_selector = /(?:\A|\s)[A-Z][A-Z0-9_]*=\S+(?:\s|\z)/
    # Named environment selectors deliberately do not use this generic branch:
    # they are valid only when environment_selector finds a complete NAME=value
    # assignment, including in forms such as "environment variable: NAME=value".
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
