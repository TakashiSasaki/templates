#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-core-profile-contracts.rb", __dir__)
orchestrator = File.expand_path("validate-profile-contracts.rb", __dir__)
repository_root = File.expand_path("../..", __dir__)
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

canonical_validation_docs = {
  "template/AGENTS.md" => [
    "Run the supported profile-aware validation entry point:",
    "focused direct validators and shared-model rule validators",
    "Some focused validators retain bounded contract-specific Markdown parsing"
  ],
  "template/README.md" => [
    "Run the supported profile-aware validation entry point:",
    "focused direct validators and shared-model rule validators",
    "Some focused direct validators retain their own bounded Markdown parsing"
  ],
  "CONTRIBUTING.md" => [
    "Run the supported profile-aware validation entry point:",
    "This fixture matrix is the stable baseline"
  ],
  "template/docs/skill-profiles.md" => [
    "Run the supported profile-aware validation entry point:",
    "focused direct validators and shared-model rule validators",
    "Focused validators may retain bounded parser logic"
  ]
}
stale_validation_markers = [
  "During the Phase 2",
  "compatibility adapter assembles",
  "later validator-consolidation phase",
  "legacy validators",
  "each retained contract directly through the shared profile contract model"
]

canonical_validation_docs.each do |relative_path, required_snippets|
  path = File.join(repository_root, relative_path)
  unless File.file?(path)
    failures << "missing canonical validation document: #{relative_path}"
    next
  end

  text = File.read(path)
  required_snippets.each do |snippet|
    failures << "#{relative_path} does not describe the stable validation architecture: #{snippet.inspect}" unless text.include?(snippet)
  end
  stale_validation_markers.each do |marker|
    failures << "#{relative_path} still describes removed or overstated validation behavior: #{marker.inspect}" if text.include?(marker)
  end
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

puts "Direct profile contract, compatibility-removal, and documentation tests passed."
