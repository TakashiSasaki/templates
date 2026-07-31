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

skill_text = lambda do |profiles, working_directory: nil, route: "see INTERFACES.md", contracts: nil|
  profile_list = profiles.split(",").map(&:strip)
  expected_contracts = []
  expected_contracts << "CLI_INTERFACE.md" if profile_list.include?("packaged-cli")
  expected_contracts << "MCP_INTERFACE.md" if profile_list.include?("mcp-enabled")
  contract_value = contracts || expected_contracts.join(" and ")

  lines = [
    "Selected profiles: #{profiles}",
    "Canonical command: #{profile_list.include?('packaged-cli') ? 'skill-tool' : 'NOT APPLICABLE'}"
  ]
  lines << "Working directory: #{working_directory}" if working_directory
  lines << "Preferred agent route: #{route}" if route
  lines << "Detailed interface contract: #{contract_value}" if contract_value
  lines.join("\n") + "\n"
end

cases = [
  {
    name: "accepts matching packaged CLI summaries",
    skill: skill_text.call("packaged-cli", working_directory: "repository root"),
    files: { "CLI_INTERFACE.md" => valid_cli },
    success: true
  },
  {
    name: "accepts both selected caller contracts",
    skill: skill_text.call("packaged-cli, mcp-enabled", working_directory: "repository root"),
    files: {
      "CLI_INTERFACE.md" => valid_cli,
      "MCP_INTERFACE.md" => valid_mcp,
      "RUNTIME.md" => valid_runtime
    },
    success: true
  },
  {
    name: "rejects stale packaged CLI working-directory summary",
    skill: skill_text.call("packaged-cli", working_directory: "current directory"),
    files: { "CLI_INTERFACE.md" => valid_cli },
    success: false
  },
  {
    name: "rejects missing packaged CLI working-directory summary",
    skill: skill_text.call("packaged-cli"),
    files: { "CLI_INTERFACE.md" => valid_cli },
    success: false
  },
  {
    name: "rejects missing preferred agent route summary",
    skill: skill_text.call("packaged-cli", working_directory: "repository root", route: nil),
    files: { "CLI_INTERFACE.md" => valid_cli },
    success: false
  },
  {
    name: "rejects a non-applicable preferred agent route summary",
    skill: skill_text.call("mcp-enabled", route: "NOT APPLICABLE"),
    files: {
      "MCP_INTERFACE.md" => valid_mcp,
      "RUNTIME.md" => valid_runtime
    },
    success: false
  },
  {
    name: "rejects a wrong detailed caller contract",
    skill: skill_text.call("packaged-cli", working_directory: "repository root", contracts: "MCP_INTERFACE.md"),
    files: { "CLI_INTERFACE.md" => valid_cli },
    success: false
  },
  {
    name: "rejects a detailed caller contract with a sentinel",
    skill: skill_text.call("packaged-cli", working_directory: "repository root", contracts: "CLI_INTERFACE.md / NOT APPLICABLE"),
    files: { "CLI_INTERFACE.md" => valid_cli },
    success: false
  },
  {
    name: "accepts a concrete Streamable HTTP endpoint matching runtime selections",
    skill: skill_text.call("mcp-enabled"),
    files: {
      "MCP_INTERFACE.md" => valid_mcp,
      "RUNTIME.md" => valid_runtime
    },
    success: true
  },
  {
    name: "accepts an explicit runtime reference for a deployment-selected endpoint",
    skill: skill_text.call("mcp-enabled"),
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
    skill: skill_text.call("mcp-enabled"),
    files: {
      "MCP_INTERFACE.md" => valid_mcp.sub(":3000/mcp", ":9999/mcp"),
      "RUNTIME.md" => valid_runtime
    },
    success: false
  },
  {
    name: "rejects a Streamable HTTP endpoint with a stale path",
    skill: skill_text.call("mcp-enabled"),
    files: {
      "MCP_INTERFACE.md" => valid_mcp.sub("/mcp", "/wrong"),
      "RUNTIME.md" => valid_runtime
    },
    success: false
  },
  {
    name: "rejects a Streamable HTTP endpoint with a stale host",
    skill: skill_text.call("mcp-enabled"),
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

puts "Interface endpoint and operational-summary tests passed."
