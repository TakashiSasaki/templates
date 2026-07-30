#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "rbconfig"
require "tmpdir"

validators = [
  File.expand_path("validate-interface-routing-contract.rb", __dir__),
  File.expand_path("validate-decomposed-interface-contracts.rb", __dir__)
].freeze

valid_cli_router = <<~MARKDOWN
  # Public interface selection contract

  ## Status

  Selection status: SELECTED

  ## Execution policy

  Preferred agent interface: installed human CLI command
  Fallback 1: NONE
  Fallback 2: NONE

  ## Contract index

  CLI_INTERFACE.md is authoritative for caller-visible CLI behavior.

  ## Cross-interface invariants

  All routes preserve authorization, confirmation, and result semantics.

  ## Availability and failure behavior

  Unavailable preferred interface behavior: report that no permitted fallback is configured
  Fallback activation conditions: no fallback is activated
  Failure classification exposed to callers: distinguish unavailability, refusal, and domain failure

  ## Decision rationale

  Rationale: use the installed command and avoid implicit process startup when it is unavailable.
MARKDOWN

valid_mcp_router = <<~MARKDOWN
  # Public interface selection contract

  ## Status

  Selection status: SELECTED

  ## Execution policy

  Preferred agent interface: native MCP tool already registered in the host
  Fallback 1: NONE
  Fallback 2: NONE

  ## Contract index

  MCP_INTERFACE.md is authoritative for caller-visible MCP behavior.

  ## Cross-interface invariants

  Every supported MCP route preserves identity, authorization, and operation semantics.

  ## Availability and failure behavior

  Unavailable preferred interface behavior: report that no permitted fallback is configured
  Fallback activation conditions: no fallback is activated
  Failure classification exposed to callers: distinguish host registration, transport, protocol, and domain failure

  ## Decision rationale

  Rationale: use the host-registered MCP route and avoid implicit process or network startup.
MARKDOWN

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
    name: "accepts completed packaged CLI routing and interface contracts",
    profile: "packaged-cli",
    files: {
      "INTERFACES.md" => valid_cli_router,
      "CLI_INTERFACE.md" => valid_cli
    },
    success: true
  },
  {
    name: "rejects an unselected routing contract",
    profile: "packaged-cli",
    files: {
      "INTERFACES.md" => valid_cli_router.sub("Selection status: SELECTED", "Selection status: UNSELECTED"),
      "CLI_INTERFACE.md" => valid_cli
    },
    success: false
  },
  {
    name: "rejects an unresolved routing fallback",
    profile: "packaged-cli",
    files: {
      "INTERFACES.md" => valid_cli_router.sub("Fallback 1: NONE", "Fallback 1: TODO"),
      "CLI_INTERFACE.md" => valid_cli
    },
    success: false
  },
  {
    name: "rejects an unresolved routing rationale",
    profile: "packaged-cli",
    files: {
      "INTERFACES.md" => valid_cli_router.sub(
        "Rationale: use the installed command and avoid implicit process startup when it is unavailable.",
        "Rationale: TODO"
      ),
      "CLI_INTERFACE.md" => valid_cli
    },
    success: false
  },
  {
    name: "rejects an unselected packaged CLI contract",
    profile: "packaged-cli",
    files: {
      "INTERFACES.md" => valid_cli_router,
      "CLI_INTERFACE.md" => valid_cli.sub("Selection status: SELECTED", "Selection status: UNSELECTED")
    },
    success: false
  },
  {
    name: "rejects an unresolved packaged CLI rationale",
    profile: "packaged-cli",
    files: {
      "INTERFACES.md" => valid_cli_router,
      "CLI_INTERFACE.md" => valid_cli.sub(
        "Rationale: a stable packaged command is required by human users and CI.",
        "Rationale: TODO"
      )
    },
    success: false
  },
  {
    name: "accepts completed MCP routing and interface contracts",
    profile: "mcp-enabled",
    files: {
      "INTERFACES.md" => valid_mcp_router,
      "MCP_INTERFACE.md" => valid_mcp
    },
    success: true
  },
  {
    name: "rejects an unselected MCP contract",
    profile: "mcp-enabled",
    files: {
      "INTERFACES.md" => valid_mcp_router,
      "MCP_INTERFACE.md" => valid_mcp.sub("Selection status: SELECTED", "Selection status: UNSELECTED")
    },
    success: false
  },
  {
    name: "rejects an unresolved MCP rationale",
    profile: "mcp-enabled",
    files: {
      "INTERFACES.md" => valid_mcp_router,
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

    diagnostics = []
    actual_success = validators.all? do |validator|
      _stdout, stderr, status = Open3.capture3(
        { "RUBYOPT" => nil },
        RbConfig.ruby,
        validator,
        chdir: directory
      )
      diagnostics << "#{File.basename(validator)}: #{stderr.strip}" unless stderr.strip.empty?
      status.success?
    end

    next if actual_success == test_case.fetch(:success)

    failures << "#{test_case.fetch(:name)}: expected success=#{test_case.fetch(:success)}, " \
                "got success=#{actual_success}; diagnostics=#{diagnostics.join(' | ').inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Decomposed interface and routing contract validation tests passed."
