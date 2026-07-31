#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-interface-routing-contract.rb", __dir__)

routing_contract = <<~MARKDOWN
  # Public interface selection contract

  ## Status

  Selection status: SELECTED

  ## Execution policy

  Preferred agent interface: installed human CLI command
  Fallback 1: browser Web interface
  Fallback 2: NONE

  ## Contract index

  CLI_INTERFACE.md and WEB_INTERFACE.md define caller-visible behavior.

  ## Cross-interface invariants

  Both routes preserve authorization, confirmation, and result semantics.

  ## Availability and failure behavior

  Unavailable preferred interface behavior: use the explicitly selected browser fallback
  Fallback activation conditions: activate only when the packaged CLI is unavailable
  Failure classification exposed to callers: distinguish CLI unavailability from browser-interface failure

  ## Decision rationale

  Rationale: prefer the packaged command and use the selected browser interface only as an explicit fallback.
MARKDOWN

cli_contract = <<~MARKDOWN
  # Packaged CLI interface contract

  ## In-place agent launcher

  Supported: NO
  Command: NOT SUPPORTED
  Delegates to: NOT SUPPORTED
MARKDOWN

cases = [
  {
    name: "accepts an explicitly selected browser fallback",
    profiles: "packaged-cli, browser-interface",
    include_web_contract: true,
    success: true
  },
  {
    name: "rejects a browser fallback without browser-interface",
    profiles: "packaged-cli",
    include_web_contract: true,
    success: false
  },
  {
    name: "rejects a browser fallback without WEB_INTERFACE.md",
    profiles: "packaged-cli, browser-interface",
    include_web_contract: false,
    success: false
  }
]

failures = []
cases.each do |test_case|
  Dir.mktmpdir("browser-routing-test") do |directory|
    File.write(File.join(directory, "SKILL.md"), "Selected profiles: #{test_case.fetch(:profiles)}\n")
    File.write(File.join(directory, "INTERFACES.md"), routing_contract)
    File.write(File.join(directory, "CLI_INTERFACE.md"), cli_contract)
    if test_case.fetch(:include_web_contract)
      File.write(File.join(directory, "WEB_INTERFACE.md"), "# Browser interface contract\n")
    end

    _stdout, stderr, status = Open3.capture3(
      { "RUBYOPT" => nil },
      RbConfig.ruby,
      validator,
      chdir: directory
    )
    next if status.success? == test_case.fetch(:success)

    failures << "#{test_case.fetch(:name)}: expected success=#{test_case.fetch(:success)}, " \
                "got #{status.success?}; diagnostics=#{stderr.strip.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Browser-interface routing tests passed."
