#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-cli-structured-output-contract.rb", __dir__)

contract = lambda do |format, version_field|
  <<~MARKDOWN
    # Packaged CLI interface contract

    ## Human CLI

    Command: skill-tool
    Working directory: repository root

    ### Structured output

    Format: #{format}
    Contract version field: #{version_field}
  MARKDOWN
end

cases = [
  ["accepts JSON with a top-level version field", "JSON", "contractVersion", true],
  ["accepts NDJSON with a dotted version path", "NDJSON", "metadata.contractVersion", true],
  ["accepts a JSON Pointer version path", "JSON", "/metadata/contractVersion", true],
  ["accepts TOML without a format whitelist entry", "TOML", "contractVersion", true],
  ["accepts Apache Avro without a format whitelist entry", "Apache Avro", "metadata.contractVersion", true],
  ["accepts a vendor media-type serialization", "application/vnd.example+json", "contractVersion", true],
  ["rejects plain-text-only output", "plain text only", "contractVersion", false],
  ["rejects human-readable output", "human readable", "contractVersion", false],
  ["rejects an unstructured declaration", "unstructured output", "contractVersion", false],
  ["rejects a generic custom nonchoice", "custom", "contractVersion", false],
  ["rejects a missing version field", "JSON", "no version field", false],
  ["rejects a prose version-field description", "JSON", "the version field in metadata", false]
]

failures = []
cases.each do |name, format, version_field, expected_success|
  Dir.mktmpdir("cli-structured-output-test") do |directory|
    File.write(File.join(directory, "SKILL.md"), "Selected profiles: packaged-cli\n")
    File.write(File.join(directory, "CLI_INTERFACE.md"), contract.call(format, version_field))

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
