#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-selected-contract-scalar-placeholders.rb", __dir__)

valid_cli = <<~MARKDOWN
  # Packaged CLI interface contract

  ## Human CLI

  Command: skill-tool
  Working directory: repository root

  ## Inputs, outputs, and side effects

  | Item | Selected behavior |
  |---|---|
  | Standard output | JSON when requested |
MARKDOWN

valid_mcp = <<~MARKDOWN
  # MCP public interface contract

  ## stdio MCP server variant

  Supported: YES
  Launch command: skill-tool mcp stdio
  Lifecycle owner: MCP host

  ## Streamable HTTP MCP server variant

  Supported: NO
  Authentication: NOT SUPPORTED
MARKDOWN

cases = [
  {
    name: "accepts concrete CLI scalar values",
    skill: "Selected profiles: packaged-cli\nCanonical command: skill-tool\nWorking directory: repository root\nPreferred agent route: see INTERFACES.md\nDetailed interface contract: CLI_INTERFACE.md\n",
    path: "CLI_INTERFACE.md",
    document: valid_cli,
    success: true
  },
  {
    name: "accepts concrete MCP scalar values",
    skill: "Selected profiles: mcp-enabled\nCanonical command: NOT APPLICABLE\nWorking directory: repository root\nPreferred agent route: see INTERFACES.md\nDetailed interface contract: MCP_INTERFACE.md\n",
    path: "MCP_INTERFACE.md",
    document: valid_mcp,
    success: true
  },
  {
    name: "rejects TBD in a CLI command",
    skill: "Selected profiles: packaged-cli\nCanonical command: TBD\nWorking directory: repository root\nPreferred agent route: see INTERFACES.md\nDetailed interface contract: CLI_INTERFACE.md\n",
    path: "CLI_INTERFACE.md",
    document: valid_cli.sub("Command: skill-tool", "Command: TBD"),
    success: false
  },
  {
    name: "rejects FIXME in a CLI working directory",
    skill: "Selected profiles: packaged-cli\nCanonical command: skill-tool\nWorking directory: FIXME\nPreferred agent route: see INTERFACES.md\nDetailed interface contract: CLI_INTERFACE.md\n",
    path: "CLI_INTERFACE.md",
    document: valid_cli.sub("Working directory: repository root", "Working directory: FIXME"),
    success: false
  },
  {
    name: "rejects PLACEHOLDER in an MCP lifecycle owner",
    skill: "Selected profiles: mcp-enabled\nCanonical command: NOT APPLICABLE\nWorking directory: repository root\nPreferred agent route: see INTERFACES.md\nDetailed interface contract: MCP_INTERFACE.md\n",
    path: "MCP_INTERFACE.md",
    document: valid_mcp.sub("Lifecycle owner: MCP host", "Lifecycle owner: PLACEHOLDER"),
    success: false
  },
  {
    name: "rejects forthcoming text in a table value",
    skill: "Selected profiles: packaged-cli\nCanonical command: skill-tool\nWorking directory: repository root\nPreferred agent route: see INTERFACES.md\nDetailed interface contract: CLI_INTERFACE.md\n",
    path: "CLI_INTERFACE.md",
    document: valid_cli.sub("| Standard output | JSON when requested |", "| Standard output | Details forthcoming. |"),
    success: false
  },
  {
    name: "rejects a placeholder operational summary",
    skill: "Selected profiles: packaged-cli\nCanonical command: skill-tool\nWorking directory: repository root\nPreferred agent route: TBD\nDetailed interface contract: CLI_INTERFACE.md\n",
    path: "CLI_INTERFACE.md",
    document: valid_cli,
    success: false
  }
]

failures = []

cases.each do |test_case|
  Dir.mktmpdir("selected-scalar-placeholder-test") do |directory|
    File.write(File.join(directory, "SKILL.md"), test_case.fetch(:skill))
    File.write(File.join(directory, test_case.fetch(:path)), test_case.fetch(:document))

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

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Selected-contract scalar placeholder tests passed."
