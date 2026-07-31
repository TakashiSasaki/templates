#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "rbconfig"
require "tmpdir"

validators = [
  File.expand_path("validate-interface-routing-contract.rb", __dir__),
  File.expand_path("validate-decomposed-interface-contracts.rb", __dir__),
  File.expand_path("validate-cli-exit-code-contract.rb", __dir__),
  File.expand_path("validate-interface-runtime-consistency.rb", __dir__)
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

  ### Exit codes

  | Code | Meaning |
  |---:|---|
  | 0 | Successful execution and successful domain result |
  | 1 | Successful execution with a negative validation, policy, or domain result |
  | 2 | Invalid command or input |
  | 4 | Operation refused by a safety, authorization, or permission rule |
  | 5 | Protocol, transport, or unexpected internal failure |

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

valid_cli_runtime = <<~MARKDOWN
  # Runtime decision record

  ## Commands

  ### Shared development commands

  | Purpose | Exact command |
  |---|---|
  | Agent launcher | NOT APPLICABLE |

  ### Packaged CLI commands

  | Purpose | Exact command |
  |---|---|
  | Human CLI | skill-tool |
MARKDOWN

valid_mcp_runtime = <<~MARKDOWN
  # Runtime decision record

  ## Commands

  ### MCP commands

  | Purpose | Exact command |
  |---|---|
  | Start stdio MCP server | skill-tool mcp stdio |
  | Start Streamable HTTP MCP server | NOT SUPPORTED |
  | Stop Streamable HTTP MCP server | NOT SUPPORTED |
  | Check MCP readiness | NOT SUPPORTED |

  ## MCP variants

  ### stdio variant

  | Item | Selected value |
  |---|---|
  | Supported | YES |
  | Server entry point | lib/mcp/server.rb |

  ### Streamable HTTP variant

  | Item | Selected value |
  |---|---|
  | Supported | NO |
  | Server entry point | NOT SUPPORTED |

  ### Bundled ad hoc MCP tool client

  | Item | Selected value |
  |---|---|
  | Supported | NO |
  | Stable public command | NOT SUPPORTED |
MARKDOWN

cli_files = {
  "INTERFACES.md" => valid_cli_router,
  "CLI_INTERFACE.md" => valid_cli,
  "RUNTIME.md" => valid_cli_runtime
}.freeze

mcp_files = {
  "INTERFACES.md" => valid_mcp_router,
  "MCP_INTERFACE.md" => valid_mcp,
  "RUNTIME.md" => valid_mcp_runtime
}.freeze

cases = [
  {
    name: "accepts completed packaged CLI routing, interface, exit-code, and runtime contracts",
    profile: "packaged-cli",
    files: cli_files,
    success: true
  },
  {
    name: "rejects an unselected routing contract",
    profile: "packaged-cli",
    files: cli_files.merge(
      "INTERFACES.md" => valid_cli_router.sub("Selection status: SELECTED", "Selection status: UNSELECTED")
    ),
    success: false
  },
  {
    name: "rejects an unresolved routing fallback",
    profile: "packaged-cli",
    files: cli_files.merge(
      "INTERFACES.md" => valid_cli_router.sub("Fallback 1: NONE", "Fallback 1: TODO")
    ),
    success: false
  },
  {
    name: "rejects a noncanonical routing category",
    profile: "packaged-cli",
    files: cli_files.merge(
      "INTERFACES.md" => valid_cli_router.sub(
        "Preferred agent interface: installed human CLI command",
        "Preferred agent interface: carrier pigeon"
      )
    ),
    success: false
  },
  {
    name: "rejects a routing category unsupported by selected profiles",
    profile: "packaged-cli",
    files: cli_files.merge(
      "INTERFACES.md" => valid_cli_router.sub(
        "Preferred agent interface: installed human CLI command",
        "Preferred agent interface: existing Streamable HTTP MCP endpoint"
      )
    ),
    success: false
  },
  {
    name: "rejects a missing CLI exit-code section",
    profile: "packaged-cli",
    files: cli_files.merge(
      "CLI_INTERFACE.md" => valid_cli.sub(
        /\n### Exit codes\n.*?(?=\n## In-place agent launcher)/m,
        ""
      )
    ),
    success: false
  },
  {
    name: "rejects an incomplete CLI exit-code mapping",
    profile: "packaged-cli",
    files: cli_files.merge(
      "CLI_INTERFACE.md" => valid_cli.sub(
        "| 5 | Protocol, transport, or unexpected internal failure |\n",
        ""
      )
    ),
    success: false
  },
  {
    name: "rejects a CLI command mismatch with runtime",
    profile: "packaged-cli",
    files: cli_files.merge(
      "RUNTIME.md" => valid_cli_runtime.sub("| Human CLI | skill-tool |", "| Human CLI | other-tool |")
    ),
    success: false
  },
  {
    name: "accepts completed MCP routing, interface, and runtime contracts",
    profile: "mcp-enabled",
    files: mcp_files,
    success: true
  },
  {
    name: "rejects an MCP route whose transport is unsupported",
    profile: "mcp-enabled",
    files: mcp_files.merge(
      "INTERFACES.md" => valid_mcp_router.sub(
        "Preferred agent interface: native MCP tool already registered in the host",
        "Preferred agent interface: existing Streamable HTTP MCP endpoint"
      )
    ),
    success: false
  },
  {
    name: "rejects an MCP launch-command mismatch with runtime",
    profile: "mcp-enabled",
    files: mcp_files.merge(
      "RUNTIME.md" => valid_mcp_runtime.sub(
        "| Start stdio MCP server | skill-tool mcp stdio |",
        "| Start stdio MCP server | other-tool mcp stdio |"
      )
    ),
    success: false
  },
  {
    name: "rejects an unresolved MCP rationale",
    profile: "mcp-enabled",
    files: mcp_files.merge(
      "MCP_INTERFACE.md" => valid_mcp.sub(
        "Rationale: stdio provides bounded local MCP access without a listening socket.",
        "Rationale: TODO"
      )
    ),
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

puts "Decomposed interface, routing, exit-code, and runtime consistency tests passed."
