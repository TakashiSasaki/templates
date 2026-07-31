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

valid_web = <<~MARKDOWN
  # Optional human verification web interface

  ## Status and purpose

  Supported: YES
  Purpose: verification

  ## Human authorization and safety

  Authentication: local session
  Allowed users or network boundary: loopback users
  Confirmation policy: required for mutations
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

valid_browser_runtime = <<~MARKDOWN
  # Runtime decision record

  ## Status

  Selection status: SELECTED

  ### Browser-interface commands

  | Purpose | Exact command |
  |---|---|
  | Start human verification Web UI | bin/skill-web start |
  | Stop human verification Web UI | bin/skill-web stop |
  | Check human verification Web UI readiness | bin/skill-web ready |

  ## Optional human verification Web interface deployment

  | Item | Selected value |
  |---|---|
  | Supported | YES |
  | Web runtime or entry point | bin/skill-web |
  | Enablement configuration | SKILL_WEB_UI=1 |
MARKDOWN

valid_headless_runtime = <<~MARKDOWN
  # Runtime decision record

  ## Status

  Selection status: SELECTED

  ### Headless-service commands

  | Purpose | Exact command |
  |---|---|
  | Start headless service | bin/skill-service start |
  | Stop headless service | bin/skill-service stop |
  | Check headless service readiness | bin/skill-service ready |

  ## Headless service deployment

  | Item | Selected value |
  |---|---|
  | Supported | YES |
  | Service runtime or entry point | bin/skill-service |
  | Authentication | bearer token from secret store |
  | Authorization | operation allowlist |
MARKDOWN

valid_script_runtime = <<~MARKDOWN
  # Runtime decision record

  ## Status

  Selection status: SELECTED

  ## Primary implementation

  | Item | Selected value |
  |---|---|
  | Language | Ruby |
  | Runtime | CRuby |
MARKDOWN

cli_skill = "Selected profiles: packaged-cli\nCanonical command: skill-tool\nWorking directory: repository root\nPreferred agent route: see INTERFACES.md\nDetailed interface contract: CLI_INTERFACE.md\n"
mcp_skill = "Selected profiles: mcp-enabled\nCanonical command: NOT APPLICABLE\nWorking directory: repository root\nPreferred agent route: see INTERFACES.md\nDetailed interface contract: MCP_INTERFACE.md\n"
browser_skill = "Selected profiles: browser-interface\nCanonical command: NOT APPLICABLE\nWorking directory: repository root\nPreferred agent route: NOT APPLICABLE\nDetailed interface contract: NOT APPLICABLE\n"
headless_skill = "Selected profiles: headless-service\nCanonical command: NOT APPLICABLE\nWorking directory: repository root\nPreferred agent route: NOT APPLICABLE\nDetailed interface contract: NOT APPLICABLE\n"
combined_skill = "Selected profiles: packaged-cli, browser-interface\nCanonical command: skill-tool\nWorking directory: repository root\nPreferred agent route: see INTERFACES.md\nDetailed interface contract: CLI_INTERFACE.md\n"
script_skill = "Selected profiles: script-assisted\nCanonical command: NOT APPLICABLE\nWorking directory: repository root\n"

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
browser_files = {
  "WEB_INTERFACE.md" => valid_web,
  "RUNTIME.md" => valid_browser_runtime
}.freeze
headless_files = {
  "RUNTIME.md" => valid_headless_runtime
}.freeze
combined_runtime = valid_cli_runtime + "\n" + valid_browser_runtime.sub(/\A# Runtime decision record.*?Selection status: SELECTED\n/m, "")
combined_files = cli_files.merge(
  "WEB_INTERFACE.md" => valid_web,
  "RUNTIME.md" => combined_runtime
).freeze

cases = [
  { name: "accepts concrete CLI scalar values", skill: cli_skill, files: cli_files, success: true },
  { name: "accepts concrete MCP scalar values", skill: mcp_skill, files: mcp_files, success: true },
  { name: "accepts concrete browser scalar values", skill: browser_skill, files: browser_files, success: true },
  { name: "accepts concrete headless-service scalar values", skill: headless_skill, files: headless_files, success: true },
  {
    name: "accepts an optional script-assisted runtime record",
    skill: script_skill,
    files: { "RUNTIME.md" => valid_script_runtime },
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
    name: "rejects TBD authentication in WEB_INTERFACE.md",
    skill: browser_skill,
    files: browser_files.merge(
      "WEB_INTERFACE.md" => valid_web.sub("Authentication: local session", "Authentication: TBD")
    ),
    success: false
  },
  {
    name: "rejects a browser runtime placeholder",
    skill: browser_skill,
    files: browser_files.merge(
      "RUNTIME.md" => valid_browser_runtime.sub("| Enablement configuration | SKILL_WEB_UI=1 |", "| Enablement configuration | TBD |")
    ),
    success: false
  },
  {
    name: "rejects a browser runtime placeholder in a combined profile",
    skill: combined_skill,
    files: combined_files.merge(
      "RUNTIME.md" => combined_runtime.sub("| Enablement configuration | SKILL_WEB_UI=1 |", "| Enablement configuration | TBD |")
    ),
    success: false
  },
  {
    name: "rejects headless-service authentication TBD",
    skill: headless_skill,
    files: headless_files.merge(
      "RUNTIME.md" => valid_headless_runtime.sub("| Authentication | bearer token from secret store |", "| Authentication | TBD |")
    ),
    success: false
  },
  {
    name: "rejects a placeholder in an optional script-assisted runtime",
    skill: script_skill,
    files: {
      "RUNTIME.md" => valid_script_runtime.sub("| Runtime | CRuby |", "| Runtime | TBD |")
    },
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

puts "Selected routing, interface, and runtime scalar placeholder tests passed."
