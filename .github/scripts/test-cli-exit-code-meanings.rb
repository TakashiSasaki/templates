#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-cli-exit-code-contract.rb", __dir__)

cli_contract = lambda do |zero_meaning, nonzero_meaning|
  <<~MARKDOWN
    # Packaged CLI interface contract

    ## Human CLI

    ### Exit codes

    | Code | Meaning |
    |---:|---|
    | 0 | #{zero_meaning} |
    | 1 | #{nonzero_meaning} |
  MARKDOWN
end

cases = [
  ["accepts an explicit successful zero meaning", "Successful execution", "Negative domain result", true],
  ["accepts a successfully completed zero meaning", "Command completed successfully", "Invalid invocation", true],
  ["rejects a negative outcome as the zero meaning", "Negative domain result", "Invalid invocation", false],
  ["rejects a failure as the zero meaning", "Execution failure", "Invalid invocation", false],
  ["rejects negated success as the zero meaning", "Not successful", "Invalid invocation", false],
  ["rejects NONE as an exit-code meaning", "Successful execution", "NONE", false],
  ["rejects NOT APPLICABLE as an exit-code meaning", "Successful execution", "NOT APPLICABLE", false],
  ["rejects NOT SUPPORTED as an exit-code meaning", "Successful execution", "NOT SUPPORTED", false],
  ["rejects TBD as an exit-code meaning", "Successful execution", "TBD", false]
]

failures = []
cases.each do |name, zero_meaning, nonzero_meaning, expected_success|
  Dir.mktmpdir("cli-exit-code-meaning-test") do |directory|
    File.write(File.join(directory, "SKILL.md"), "Selected profiles: packaged-cli\n")
    File.write(File.join(directory, "CLI_INTERFACE.md"), cli_contract.call(zero_meaning, nonzero_meaning))

    _stdout, stderr, status = Open3.capture3(
      { "RUBYOPT" => nil },
      RbConfig.ruby,
      validator,
      chdir: directory
    )
    next if status.success? == expected_success

    failures << "#{name}: expected success=#{expected_success}, got #{status.success?}; " \
                "diagnostics=#{stderr.strip.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "CLI exit-code meaning tests passed."
