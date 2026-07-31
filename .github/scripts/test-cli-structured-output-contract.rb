#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-cli-structured-output-contract.rb", __dir__)

contract = lambda do |mode_selector, format, version_field|
  <<~MARKDOWN
    # Packaged CLI interface contract

    ## Human CLI

    Command: skill-tool
    Working directory: repository root

    ### Structured output

    Mode selector: #{mode_selector}
    Format: #{format}
    Contract version field: #{version_field}
  MARKDOWN
end

cases = [
  ["accepts a long option with a separate value", "--output json", "JSON", "contractVersion", true],
  ["accepts a boolean JSON flag", "--json", "NDJSON", "metadata.contractVersion", true],
  ["accepts an environment assignment", "SKILL_OUTPUT=json", "JSON", "/metadata/contractVersion", true],
  ["accepts an explicitly named subcommand", "subcommand: export-json", "TOML", "contractVersion", true],
  ["accepts Apache Avro without a format whitelist entry", "--format avro", "Apache Avro", "metadata.contractVersion", true],
  ["accepts a vendor media-type serialization", "--media-type application/vnd.example+json", "application/vnd.example+json", "contractVersion", true],
  ["rejects a missing mode selector", nil, "JSON", "contractVersion", false],
  ["rejects an unresolved mode selector", "TODO", "JSON", "contractVersion", false],
  ["rejects a vague automatic selector", "automatic", "JSON", "contractVersion", false],
  ["rejects a prose selector description", "use the structured mode documented elsewhere", "JSON", "contractVersion", false],
  ["rejects plain-text-only output", "--output text", "plain text only", "contractVersion", false],
  ["rejects human-readable output", "--human", "human readable", "contractVersion", false],
  ["rejects an unstructured declaration", "--output raw", "unstructured output", "contractVersion", false],
  ["rejects a generic custom nonchoice", "--output custom", "custom", "contractVersion", false],
  ["rejects a missing version field", "--json", "JSON", "no version field", false],
  ["rejects a prose version-field description", "--json", "JSON", "the version field in metadata", false]
]

failures = []
cases.each do |name, mode_selector, format, version_field, expected_success|
  Dir.mktmpdir("cli-structured-output-test") do |directory|
    File.write(File.join(directory, "SKILL.md"), "Selected profiles: packaged-cli\n")
    File.write(File.join(directory, "CLI_INTERFACE.md"), contract.call(mode_selector, format, version_field))

    _stdout, stderr, status = Open3.capture3(
      { "RUBYOPT" => nil },
      RbConfig.ruby,
      validator,
      chdir: directory
    )
    next if status.success? == expected_success

    failures << "#{name}: expected success=#{expected_success}, got #{status.success?}; diagnostics=#{stderr.strip.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "CLI structured-output contract tests passed."
