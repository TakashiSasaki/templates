#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-bundled-mcp-client-consistency.rb", __dir__)

valid_public = <<~MARKDOWN
  # MCP public interface contract

  ## Bundled ad hoc MCP tool client

  Supported: YES
  Scope: tools only
  Command: skill-tool mcp client
  Transport used: stdio
  Negotiation and compatibility behavior: negotiate the selected revision and fail explicitly
  Invocation scope: multiple sequential tool calls
  Interaction modes: non-interactive
  Task or extension support: NOT SUPPORTED
MARKDOWN

valid_runtime = <<~MARKDOWN
  # Runtime decision record

  ### Bundled ad hoc MCP tool client

  | Item | Selected value |
  |---|---|
  | Supported | YES |
  | Scope | tools only |
  | Stable public command | skill-tool mcp client |
  | Supported transports | stdio |
  | Negotiation and compatibility behavior | negotiate the selected revision and fail explicitly |
  | Invocation scope | multiple sequential tool calls |
  | Interaction modes | non-interactive |
  | Task or extension support | NOT SUPPORTED |
MARKDOWN

cases = [
  {
    name: "accepts matching bundled-client selections",
    public: valid_public,
    runtime: valid_runtime,
    success: true
  },
  {
    name: "accepts explicit runtime references",
    public: valid_public
      .sub("Scope: tools only", "Scope: see RUNTIME.md")
      .sub(
        "Negotiation and compatibility behavior: negotiate the selected revision and fail explicitly",
        "Negotiation and compatibility behavior: see RUNTIME.md"
      )
      .sub("Invocation scope: multiple sequential tool calls", "Invocation scope: see RUNTIME.md")
      .sub("Interaction modes: non-interactive", "Interaction modes: see RUNTIME.md")
      .sub("Task or extension support: NOT SUPPORTED", "Task or extension support: see RUNTIME.md"),
    runtime: valid_runtime,
    success: true
  },
  {
    name: "rejects a bundled-client scope mismatch",
    public: valid_public.sub("Scope: tools only", "Scope: broader MCP client"),
    runtime: valid_runtime,
    success: false
  },
  {
    name: "rejects a bundled-client negotiation mismatch",
    public: valid_public.sub(
      "Negotiation and compatibility behavior: negotiate the selected revision and fail explicitly",
      "Negotiation and compatibility behavior: use a fixed revision without fallback"
    ),
    runtime: valid_runtime,
    success: false
  },
  {
    name: "rejects a bundled-client invocation-scope mismatch",
    public: valid_public.sub("Invocation scope: multiple sequential tool calls", "Invocation scope: one tool call"),
    runtime: valid_runtime,
    success: false
  },
  {
    name: "rejects a bundled-client interaction-mode mismatch",
    public: valid_public.sub("Interaction modes: non-interactive", "Interaction modes: interactive"),
    runtime: valid_runtime,
    success: false
  },
  {
    name: "rejects a bundled-client extension-support mismatch",
    public: valid_public.sub("Task or extension support: NOT SUPPORTED", "Task or extension support: tasks"),
    runtime: valid_runtime,
    success: false
  }
]

failures = []

cases.each do |test_case|
  Dir.mktmpdir("bundled-mcp-client-consistency-test") do |directory|
    File.write(File.join(directory, "SKILL.md"), "Selected profiles: mcp-enabled\n")
    File.write(File.join(directory, "MCP_INTERFACE.md"), test_case.fetch(:public))
    File.write(File.join(directory, "RUNTIME.md"), test_case.fetch(:runtime))

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

puts "Bundled MCP client consistency tests passed."
