#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-cli-exit-code-contract.rb", __dir__)

cli_contract = lambda do |meaning|
  <<~MARKDOWN
    # Packaged CLI interface contract

    ## Human CLI

    ### Exit codes

    | Code | Meaning |
    |---:|---|
    | 0 | Successful execution |
    | 1 | #{meaning} |
  MARKDOWN
end

cases = [
  ["accepts a concrete exit-code meaning", "Negative domain result", true],
  ["rejects NONE as an exit-code meaning", "NONE", false],
  ["rejects NOT APPLICABLE as an exit-code meaning", "NOT APPLICABLE", false],
  ["rejects NOT SUPPORTED as an exit-code meaning", "NOT SUPPORTED", false]
]

failures = []
cases.each do |name, meaning, expected_success|
  Dir.mktmpdir("cli-exit-code-meaning-test") do |directory|
    File.write(File.join(directory, "SKILL.md"), "Selected profiles: packaged-cli\n")
    File.write(File.join(directory, "CLI_INTERFACE.md"), cli_contract.call(meaning))

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
