#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-core-profile-contracts.rb", __dir__)
orchestrator = File.expand_path("validate-profile-contracts.rb", __dir__)
obsolete_paths = %w[
  decomposed-interface-compat.rb
  validate-selected-profiles.rb
  validate-selected-profiles-core.rb
].map { |path| File.expand_path(path, __dir__) }

failures = []

obsolete_paths.each do |path|
  failures << "obsolete compatibility file remains: #{path}" if File.exist?(path)
end

orchestrator_text = File.read(orchestrator)
if orchestrator_text.include?("decomposed-interface-compat") || orchestrator_text.include?("legacy_environment")
  failures << "validate-profile-contracts.rb still injects the decomposed interface compatibility layer"
end

skill = <<~MARKDOWN
  ---
  name: direct-profile-test
  description: Concrete instruction-only skill used by the validator regression test.
  ---

  # Direct profile test

  Selected profiles: instruction-only

  ## Purpose

  Perform a deterministic test operation.

  ## Use this skill when

  Use it for direct profile validation tests.

  ## Workflow

  Read the input and return the required result.

  ## Output requirements

  Return a concise result.

  ## Validation

  Confirm that the result matches the input contract.

  ## Safety and approval

  Do not modify external state.
MARKDOWN

cases = [
  {
    name: "accepts a complete instruction-only skill without optional contracts",
    profiles: "instruction-only",
    files: {},
    success: true
  },
  {
    name: "rejects CLI_INTERFACE.md without packaged-cli",
    profiles: "instruction-only",
    files: { "CLI_INTERFACE.md" => "# Unsupported CLI contract\n" },
    success: false
  },
  {
    name: "requires CLI_INTERFACE.md for packaged-cli",
    profiles: "packaged-cli",
    files: {},
    success: false
  },
  {
    name: "requires MCP_INTERFACE.md for mcp-enabled",
    profiles: "mcp-enabled",
    files: {},
    success: false
  }
]

cases.each do |test_case|
  Dir.mktmpdir("direct-profile-contract-test") do |directory|
    File.write(
      File.join(directory, "SKILL.md"),
      skill.sub("Selected profiles: instruction-only", "Selected profiles: #{test_case.fetch(:profiles)}")
    )
    test_case.fetch(:files).each do |path, content|
      absolute = File.join(directory, path)
      FileUtils.mkdir_p(File.dirname(absolute))
      File.write(absolute, content)
    end

    Open3.capture3("git", "init", "--quiet", chdir: directory)
    Open3.capture3("git", "add", ".", chdir: directory)
    _stdout, stderr, status = Open3.capture3(
      { "RUBYOPT" => nil },
      RbConfig.ruby,
      validator,
      chdir: directory
    )

    next if status.success? == test_case.fetch(:success)

    failures << "#{test_case.fetch(:name)}: expected success=#{test_case.fetch(:success)}, " \
                "got success=#{status.success?}; diagnostics=#{stderr.strip.inspect}"
  end
end

Dir.mktmpdir("explicit-validator-path-test") do |directory|
  File.write(File.join(directory, "SKILL.md"), skill)
  Open3.capture3("git", "init", "--quiet", chdir: directory)
  Open3.capture3("git", "add", ".", chdir: directory)

  requested = "does/not/exist/validate-core-profile-contracts.rb"
  _stdout, stderr, status = Open3.capture3(
    { "RUBYOPT" => nil },
    RbConfig.ruby,
    orchestrator,
    requested,
    chdir: directory
  )
  unless !status.success? && stderr.include?("Missing profile validator: #{requested}")
    failures << "explicit validator paths must fail exactly when missing; " \
                "status=#{status.exitstatus.inspect}, diagnostics=#{stderr.strip.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Direct profile contract and compatibility-removal tests passed."
