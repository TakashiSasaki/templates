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

pages_workflow_path = File.expand_path("../workflows/pages.yml", __dir__)
unless File.file?(pages_workflow_path)
  warn "Missing documentation publishing workflow: #{pages_workflow_path}"
  exit 1
end

pages_workflow = File.read(pages_workflow_path)
%w[CLI_INTERFACE.md MCP_INTERFACE.md].each do |path|
  unless /^\s*-\s+#{Regexp.escape(path)}\s*$/.match?(pages_workflow)
    warn "Publish template documentation must trigger when #{path} changes."
    exit 1
  end
end

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
  | 0 | Successful execution |
  | 1 | Negative domain result |
  | 2 | Invalid invocation or internal failure |

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

  Supported: YES
  Start command: skill-tool mcp http
  Stop command or shutdown method: skill-tool mcp stop
  Endpoint URL: http://127.0.0.1:3000/mcp
  Bind address: 127.0.0.1
  Port selection: 3000
  Supported protocol eras: modern
  Revision-specific state model: request-scoped
  Authentication: bearer token
  Health/readiness check: skill-tool mcp ready

  ## Bundled ad hoc MCP tool client

  Supported: NO
  Scope: NOT SUPPORTED
  Command: NOT SUPPORTED
  Transport used: NOT SUPPORTED
  Negotiation and compatibility behavior: NOT SUPPORTED
  Invocation scope: NOT SUPPORTED
  Interaction modes: NOT SUPPORTED
  Task or extension support: NOT SUPPORTED

  ### Tool inventory, schemas, and caching

  Tool-list pagination follows opaque cursors and preserves every ordered raw page and unknown field.

  ### Lossless paginated tool-list output

  Lossless output stores each received page without merging page-level metadata or cache hints.

  ### Tool-call results and errors

  Tool-call output preserves the complete MCP result and distinguishes transport, protocol, domain-error, and success outcomes.

  ### Multiple calls and application state

  Sequential calls remain independent MCP requests and required state is represented by documented identifiers.

  ### Selected modern multi-round-trip requests

  Non-interactive mode returns input-required results unchanged; explicit responses are required before retrying.

  ### Selected initialization-era server-to-client requests

  Initialization-era capabilities are not advertised unless their handlers and terminal-response behavior are implemented.

  ### Cancellation, tasks, and extensions

  Cancellation uses the selected revision and transport behavior, then cleans up requests, connections, and child processes.

  ### Ownership and workspace policy

  The MCP host owns the stdio process and applies the same documented workspace restrictions as other maintained adapters.

  ## Semantic-equivalence and test requirements

  Both MCP transports use the shared operation registry and contract fixtures.

  ## Decision rationale

  Rationale: stdio and loopback HTTP provide bounded MCP access for local hosts and existing clients.
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
  | Start Streamable HTTP MCP server | skill-tool mcp http |
  | Stop Streamable HTTP MCP server | skill-tool mcp stop |
  | Check MCP readiness | skill-tool mcp ready |

  ## MCP variants

  ### stdio variant

  | Item | Selected value |
  |---|---|
  | Supported | YES |
  | Server entry point | lib/mcp/server.rb |
  | Lifecycle owner | MCP host |

  ### Streamable HTTP variant

  | Item | Selected value |
  |---|---|
  | Supported | YES |
  | Server entry point | lib/mcp/http_server.rb |
  | Default bind address | 127.0.0.1 |
  | Port | 3000 |
  | Supported protocol eras | modern |
  | Revision-specific state model | request-scoped |
  | Authentication | bearer token |

  ### Bundled ad hoc MCP tool client

  | Item | Selected value |
  |---|---|
  | Supported | NO |
  | Stable public command | NOT SUPPORTED |
  | Supported transports | NOT SUPPORTED |
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

remove_section = lambda do |document, heading|
  level = heading[/\A#+/].length
  boundary = level == 2 ? "^##\\s|\\z" : "^(?:##|###)\\s|\\z"
  document.sub(
    Regexp.new("^#{Regexp.escape(heading)}\\s*$\\n.*?(?=#{boundary})", Regexp::MULTILINE),
    ""
  )
end

cases = [
  {
    name: "accepts a compact three-code CLI mapping",
    profile: "packaged-cli",
    files: cli_files,
    success: true
  },
  {
    name: "rejects a CLI exit-code mapping with no nonzero result",
    profile: "packaged-cli",
    files: cli_files.merge(
      "CLI_INTERFACE.md" => valid_cli.gsub(/^\| [12] \|.*\n/, "")
    ),
    success: false
  },
  {
    name: "rejects a negative CLI exit code",
    profile: "packaged-cli",
    files: cli_files.merge(
      "CLI_INTERFACE.md" => valid_cli.sub("| 2 | Invalid invocation or internal failure |", "| -1 | Invalid invocation or internal failure |")
    ),
    success: false
  },
  {
    name: "rejects a CLI exit code above 255",
    profile: "packaged-cli",
    files: cli_files.merge(
      "CLI_INTERFACE.md" => valid_cli.sub("| 2 | Invalid invocation or internal failure |", "| 256 | Invalid invocation or internal failure |")
    ),
    success: false
  },
  {
    name: "rejects a missing CLI exit-code section",
    profile: "packaged-cli",
    files: cli_files.merge(
      "CLI_INTERFACE.md" => remove_section.call(valid_cli, "### Exit codes")
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
    name: "rejects a CLI command mismatch with runtime",
    profile: "packaged-cli",
    files: cli_files.merge(
      "RUNTIME.md" => valid_cli_runtime.sub("| Human CLI | skill-tool |", "| Human CLI | other-tool |")
    ),
    success: false
  },
  {
    name: "rejects a stale SKILL.md canonical command",
    profile: "packaged-cli",
    canonical_command: "other-tool",
    files: cli_files,
    success: false
  },
  {
    name: "accepts completed MCP caller-visible and runtime selections",
    profile: "mcp-enabled",
    files: mcp_files,
    success: true
  },
  {
    name: "accepts explicit references to runtime-owned MCP selections",
    profile: "mcp-enabled",
    files: mcp_files.merge(
      "MCP_INTERFACE.md" => valid_mcp
        .sub("Lifecycle owner: MCP host", "Lifecycle owner: see RUNTIME.md")
        .sub("Bind address: 127.0.0.1", "Bind address: see RUNTIME.md")
        .sub("Port selection: 3000", "Port selection: see RUNTIME.md")
        .sub("Supported protocol eras: modern", "Supported protocol eras: see RUNTIME.md")
        .sub("Revision-specific state model: request-scoped", "Revision-specific state model: see RUNTIME.md")
        .sub("Authentication: bearer token", "Authentication: see RUNTIME.md")
    ),
    success: true
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
    name: "rejects a stdio lifecycle-owner mismatch with runtime",
    profile: "mcp-enabled",
    files: mcp_files.merge(
      "RUNTIME.md" => valid_mcp_runtime.sub("| Lifecycle owner | MCP host |", "| Lifecycle owner | bundled tool client |")
    ),
    success: false
  },
  {
    name: "rejects an HTTP bind-address mismatch with runtime",
    profile: "mcp-enabled",
    files: mcp_files.merge(
      "RUNTIME.md" => valid_mcp_runtime.sub("| Default bind address | 127.0.0.1 |", "| Default bind address | 0.0.0.0 |")
    ),
    success: false
  }
]

[
  "### Tool inventory, schemas, and caching",
  "### Lossless paginated tool-list output",
  "### Tool-call results and errors",
  "### Multiple calls and application state",
  "### Selected modern multi-round-trip requests",
  "### Selected initialization-era server-to-client requests",
  "### Cancellation, tasks, and extensions",
  "### Ownership and workspace policy"
].each do |heading|
  cases << {
    name: "rejects MCP contract missing #{heading}",
    profile: "mcp-enabled",
    files: mcp_files.merge(
      "MCP_INTERFACE.md" => remove_section.call(valid_mcp, heading)
    ),
    success: false
  }
end

failures = []

cases.each do |test_case|
  Dir.mktmpdir("decomposed-contract-test") do |directory|
    canonical_command = test_case.fetch(
      :canonical_command,
      test_case.fetch(:profile) == "packaged-cli" ? "skill-tool" : "NOT APPLICABLE"
    )
    File.write(
      File.join(directory, "SKILL.md"),
      "Selected profiles: #{test_case.fetch(:profile)}\nCanonical command: #{canonical_command}\n"
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

puts "Decomposed interface, routing, exit-code, runtime consistency, and publishing tests passed."
