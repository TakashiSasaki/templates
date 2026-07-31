#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-interface-summary-details.rb", __dir__)

valid_cli = <<~MARKDOWN
  # Packaged CLI interface contract

  ## Human CLI

  Command: skill-tool
  Working directory: repository root
MARKDOWN

valid_mcp = <<~MARKDOWN
  # MCP public interface contract

  ## Streamable HTTP MCP server variant

  Supported: YES
  Endpoint URL: http://127.0.0.1:3000/mcp
MARKDOWN

valid_runtime = <<~MARKDOWN
  # Runtime decision record

  ### Streamable HTTP variant

  | Item | Selected value |
  |---|---|
  | Supported | YES |
  | Endpoint path | /mcp |
  | Default bind address | 127.0.0.1 |
  | Port | 3000 |
MARKDOWN

cases = [
  {
    name: "accepts matching packaged CLI working-directory summary",
    skill: "Selected profiles: packaged-cli\nCanonical command: skill-tool\nWorking directory: repository root\n",
    files: { "CLI_INTERFACE.md" => valid_cli },
    success: true
  },
  {
    name: "rejects stale packaged CLI working-directory summary",
    skill: "Selected profiles: packaged-cli\nCanonical command: skill-tool\nWorking directory: current directory\n",
    files: { "CLI_INTERFACE.md" => valid_cli },
    success: false
  },
  {
    name: "rejects missing packaged CLI working-directory summary",
    skill: "Selected profiles: packaged-cli\nCanonical command: skill-tool\n",
    files: { "CLI_INTERFACE.md" => valid_cli },
    success: false
  },
  {
    name: "accepts a concrete Streamable HTTP endpoint matching runtime selections",
    skill: "Selected profiles: mcp-enabled\n",
    files: {
      "MCP_INTERFACE.md" => valid_mcp,
      "RUNTIME.md" => valid_runtime
    },
    success: true
  },
  {
    name: "accepts an explicit runtime reference for a deployment-selected endpoint",
    skill: "Selected profiles: mcp-enabled\n",
    files: {
      "MCP_INTERFACE.md" => valid_mcp.sub(
        "Endpoint URL: http://127.0.0.1:3000/mcp",
        "Endpoint URL: see RUNTIME.md"
      ),
      "RUNTIME.md" => valid_runtime.sub("| Port | 3000 |", "| Port | deployment-selected |")
    },
    success: true
  },
  {
    name: "rejects a Streamable HTTP endpoint with a stale port",
    skill: "Selected profiles: mcp-enabled\n",
    files: {
      "MCP_INTERFACE.md" => valid_mcp.sub(":3000/mcp", ":9999/mcp"),
      "RUNTIME.md" => valid_runtime
    },
    success: false
  },
  {
    name: "rejects a Streamable HTTP endpoint with a stale path",
    skill: "Selected profiles: mcp-enabled\n",
    files: {
      "MCP_INTERFACE.md" => valid_mcp.sub("/mcp", "/wrong"),
      "RUNTIME.md" => valid_runtime
    },
    success: false
  },
  {
    name: "rejects a Streamable HTTP endpoint with a stale host",
    skill: "Selected profiles: mcp-enabled\n",
    files: {
      "MCP_INTERFACE.md" => valid_mcp.sub("127.0.0.1", "localhost"),
      "RUNTIME.md" => valid_runtime
    },
    success: false
  }
]

failures = []

cases.each do |test_case|
  Dir.mktmpdir("interface-summary-details-test") do |directory|
    File.write(File.join(directory, "SKILL.md"), test_case.fetch(:skill))
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
                "got success=#{actual_success}; diagnostics=#{stderr.strip.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Interface endpoint and working-directory summary tests passed."
