#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-selected-contract-scalar-placeholders.rb", __dir__)

valid_routing = <<~MARKDOWN
  # Public interface selection contract

  ## Status

  Selection status: SELECTED

  ## Execution policy

  Preferred agent interface: installed human CLI command
  Fallback 1: NONE
  Fallback 2: NONE

  ## Contract index

  The selected profile-specific interface document is authoritative for caller-visible behavior.

  ## Cross-interface invariants

  All maintained routes preserve authorization, confirmation, and result semantics.

  ## Availability and failure behavior

  Unavailable preferred interface behavior: report unavailability
  Fallback activation conditions: use only documented fallbacks
  Failure classification exposed to callers: distinguish unavailability, refusal, and execution failure

  ## Decision rationale

  Rationale: keep route selection explicit and deterministic.
MARKDOWN

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

valid_cli_runtime = <<~MARKDOWN
  # Runtime decision record

  ## Status

  Selection status: SELECTED

  ### Packaged CLI commands

  | Purpose | Exact command |
  |---|---|
  | Human CLI | skill-tool |
MARKDOWN

valid_mcp_runtime = <<~MARKDOWN
  # Runtime decision record

  ## Status

  Selection status: SELECTED

  ### stdio variant

  | Item | Selected value |
  |---|---|
  | Supported | YES |
  | Server entry point | lib/mcp/server.rb |
  | Lifecycle owner | MCP host |

  ### Streamable HTTP variant

  | Item | Selected value |
  |---|---|
  | Supported | NO |
MARKDOWN

cli_skill = "Selected profiles: packaged-cli\nCanonical command: skill-tool\nWorking directory: repository root\nPreferred agent route: see INTERFACES.md\nDetailed interface contract: CLI_INTERFACE.md\n"
mcp_skill = "Selected profiles: mcp-enabled\nCanonical command: NOT APPLICABLE\nWorking directory: repository root\nPreferred agent route: see INTERFACES.md\nDetailed interface contract: MCP_INTERFACE.md\n"

cli_files = {
  "INTERFACES.md" => valid_routing,
  "CLI_INTERFACE.md" => valid_cli,
  "RUNTIME.md" => valid_cli_runtime
}.freeze
mcp_files = {
  "INTERFACES.md" => valid_routing,
  "MCP_INTERFACE.md" => valid_mcp,
  "RUNTIME.md" => valid_mcp_runtime
}.freeze

cases = [
  {
    name: "accepts concrete CLI scalar values",
    skill: cli_skill,
    files: cli_files,
    success: true
  },
  {
    name: "accepts concrete MCP scalar values",
    skill: mcp_skill,
    files: mcp_files,
    success: true
  },
  {
    name: "rejects TBD in the routing contract index",
    skill: cli_skill,
    files: cli_files.merge(
      "INTERFACES.md" => valid_routing.sub(
        "The selected profile-specific interface document is authoritative for caller-visible behavior.",
        "TBD"
      )
    ),
    success: false
  },
  {
    name: "rejects FIXME in routing cross-interface invariants",
    skill: cli_skill,
    files: cli_files.merge(
      "INTERFACES.md" => valid_routing.sub(
        "All maintained routes preserve authorization, confirmation, and result semantics.",
        "FIXME"
      )
    ),
    success: false
  },
  {
    name: "rejects TBD in a CLI command",
    skill: cli_skill.sub("Canonical command: skill-tool", "Canonical command: TBD"),
    files: cli_files.merge(
      "CLI_INTERFACE.md" => valid_cli.sub("Command: skill-tool", "Command: TBD"),
      "RUNTIME.md" => valid_cli_runtime.sub("| Human CLI | skill-tool |", "| Human CLI | TBD |")
    ),
    success: false
  },
  {
    name: "rejects FIXME in a CLI working directory",
    skill: cli_skill.sub("Working directory: repository root", "Working directory: FIXME"),
    files: cli_files.merge(
      "CLI_INTERFACE.md" => valid_cli.sub("Working directory: repository root", "Working directory: FIXME")
    ),
    success: false
  },
  {
    name: "rejects PLACEHOLDER in an MCP lifecycle owner",
    skill: mcp_skill,
    files: mcp_files.merge(
      "MCP_INTERFACE.md" => valid_mcp.sub("Lifecycle owner: MCP host", "Lifecycle owner: PLACEHOLDER"),
      "RUNTIME.md" => valid_mcp_runtime.sub("| Lifecycle owner | MCP host |", "| Lifecycle owner | PLACEHOLDER |")
    ),
    success: false
  },
  {
    name: "rejects forthcoming text in a table value",
    skill: cli_skill,
    files: cli_files.merge(
      "CLI_INTERFACE.md" => valid_cli.sub("| Standard output | JSON when requested |", "| Standard output | Details forthcoming. |")
    ),
    success: false
  },
  {
    name: "rejects a placeholder operational summary",
    skill: cli_skill.sub("Preferred agent route: see INTERFACES.md", "Preferred agent route: TBD"),
    files: cli_files,
    success: false
  },
  {
    name: "rejects a runtime scalar placeholder behind a concrete public contract",
    skill: cli_skill,
    files: cli_files.merge(
      "RUNTIME.md" => valid_cli_runtime.sub("| Human CLI | skill-tool |", "| Human CLI | TBD |")
    ),
    success: false
  }
]

failures = []

cases.each do |test_case|
  Dir.mktmpdir("selected-scalar-placeholder-test") do |directory|
    File.write(File.join(directory, "SKILL.md"), test_case.fetch(:skill))
    test_case.fetch(:files).each do |path, document|
      File.write(File.join(directory, path), document)
    end

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

puts "Selected routing, public-contract, and runtime scalar placeholder tests passed."
