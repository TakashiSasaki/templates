#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-decomposed-interface-contracts.rb", __dir__)

valid_cli = <<~MARKDOWN
  # Packaged CLI interface contract

  ## Status

  Selection status: SELECTED

  ## Human CLI

  Command: skill-tool
  Working directory: repository root

  ### Structured output

  Format: JSON
  Contract version field: contractVersion

  ## In-place agent launcher

  Supported: NO
  Command: NOT SUPPORTED
  Delegates to: NOT SUPPORTED

  ## Inputs, outputs, and side effects

  | Item | Selected behavior |
  |---|---|
  | Input forms and precedence | command options override environment defaults |
  | Standard output | human text by default and JSON when requested |
  | Standard error | diagnostics only |
  | Files or external state modified | NONE |
  | Network access | NONE |
  | Required permissions | NONE |
  | Confirmation policy | required before destructive operations |
  | Timeout and cancellation | caller cancellation is propagated |
  | Idempotency and retry behavior | read-only operations are retryable |

  ## Compatibility and versioning

  Compatibility policy: additive structured fields are backward compatible
  Deprecation policy: deprecated options remain for one major release
  Structured contract version source: contractVersion in structured output

  ## Semantic-equivalence and test requirements

  The CLI uses the same operation implementation as other maintained adapters.

  ## Decision rationale

  Rationale: a stable packaged command is required by human users and CI.
MARKDOWN

valid_mcp = <<~MARKDOWN
  # MCP public interface contract

  ## Status

  Selection status: SELECTED

  ## MCP protocol reference

  Runtime, SDK, revision, era boundary, and schema source of truth: RUNTIME.md
  Public negotiation and fallback behavior: negotiate the configured revision and fail explicitly
  Public compatibility statement: tool names and schemas are stable within the documented contract version

  ## stdio MCP server variant

  Supported: YES
  Launch command: skill-tool mcp stdio
  Lifecycle owner: MCP host

  ## Streamable HTTP MCP server variant

  Supported: NO
  Start command: NOT SUPPORTED
  Stop command or shutdown method: NOT SUPPORTED
  Endpoint URL: NOT SUPPORTED
  Bind address: NOT SUPPORTED
  Port selection: NOT SUPPORTED
  Supported protocol eras: NOT SUPPORTED
  Revision-specific state model: NOT SUPPORTED
  Authentication: NOT SUPPORTED
  Health/readiness check: NOT SUPPORTED

  ## Bundled ad hoc MCP tool client

  Supported: NO
  Scope: NOT SUPPORTED
  Command: NOT SUPPORTED
  Transport used: NOT SUPPORTED
  Negotiation and compatibility behavior: NOT SUPPORTED
  Invocation scope: NOT SUPPORTED
  Interaction modes: NOT SUPPORTED
  Task or extension support: NOT SUPPORTED

  ## Semantic-equivalence and test requirements

  The stdio adapter uses the shared operation registry and contract fixtures.

  ## Decision rationale

  Rationale: stdio provides bounded local MCP access without a listening socket.
MARKDOWN

cases = [
  {
    name: "accepts a completed packaged CLI contract",
    profile: "packaged-cli",
    files: { "CLI_INTERFACE.md" => valid_cli },
    success: true
  },
  {
    name: "rejects an unselected packaged CLI contract",
    profile: "packaged-cli",
    files: {
      "CLI_INTERFACE.md" => valid_cli.sub("Selection status: SELECTED", "Selection status: UNSELECTED")
    },
    success: false
  },
  {
    name: "rejects an unresolved packaged CLI rationale",
    profile: "packaged-cli",
    files: {
      "CLI_INTERFACE.md" => valid_cli.sub(
        "Rationale: a stable packaged command is required by human users and CI.",
        "Rationale: TODO"
      )
    },
    success: false
  },
  {
    name: "accepts a completed MCP contract",
    profile: "mcp-enabled",
    files: { "MCP_INTERFACE.md" => valid_mcp },
    success: true
  },
  {
    name: "rejects an unselected MCP contract",
    profile: "mcp-enabled",
    files: {
      "MCP_INTERFACE.md" => valid_mcp.sub("Selection status: SELECTED", "Selection status: UNSELECTED")
    },
    success: false
  },
  {
    name: "rejects an unresolved MCP rationale",
    profile: "mcp-enabled",
    files: {
      "MCP_INTERFACE.md" => valid_mcp.sub(
        "Rationale: stdio provides bounded local MCP access without a listening socket.",
        "Rationale: TODO"
      )
    },
    success: false
  }
]

failures = []

cases.each do |test_case|
  Dir.mktmpdir("decomposed-contract-test") do |directory|
    File.write(
      File.join(directory, "SKILL.md"),
      "Selected profiles: #{test_case.fetch(:profile)}\n"
    )

    test_case.fetch(:files).each do |path, content|
      absolute_path = File.join(directory, path)
      FileUtils.mkdir_p(File.dirname(absolute_path))
      File.write(absolute_path, content)
    end

    _stdout, stderr, status = Open3.capture3(
      { "RUBYOPT" => nil },
      RbConfig.ruby,
      validator,
      chdir: directory
    )

    actual_success = status.success?
    next if actual_success == test_case.fetch(:success)

    failures << "#{test_case.fetch(:name)}: expected success=#{test_case.fetch(:success)}, " \
                "got success=#{actual_success}; stderr=#{stderr.strip.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Decomposed interface contract validation tests passed."
