#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-mcp-runtime-authority.rb", __dir__)
label = "Runtime, SDK, revision, era boundary, and schema source of truth"

contract = lambda do |declaration|
  <<~MARKDOWN
    # MCP public interface contract

    ## MCP protocol reference

    #{declaration}
    Public negotiation and fallback behavior: negotiate the configured revision and fail explicitly
    Public compatibility statement: tool names and schemas are stable
  MARKDOWN
end

cases = [
  ["accepts the required runtime authority", contract.call("#{label}: RUNTIME.md"), true],
  ["accepts a backtick-wrapped runtime authority", contract.call("#{label}: `RUNTIME.md`"), true],
  ["rejects a missing runtime authority", contract.call("Protocol authority: RUNTIME.md"), false],
  ["rejects another authority file", contract.call("#{label}: MCP_RUNTIME.md"), false],
  ["rejects an explanatory suffix", contract.call("#{label}: RUNTIME.md and docs/mcp.md"), false],
  ["rejects duplicate authority declarations", contract.call("#{label}: RUNTIME.md\n#{label}: RUNTIME.md"), false]
]

failures = []
cases.each do |name, mcp_contract, expected_success|
  Dir.mktmpdir("mcp-runtime-authority-test") do |directory|
    File.write(File.join(directory, "SKILL.md"), "Selected profiles: mcp-enabled\n")
    File.write(File.join(directory, "MCP_INTERFACE.md"), mcp_contract)

    _stdout, stderr, status = Open3.capture3(
      { "RUBYOPT" => nil },
      RbConfig.ruby,
      validator,
      chdir: directory
    )
    next if status.success? == expected_success

    failures << "#{name}: expected success=#{expected_success}, got #{status.success?}; diagnostics=#{stderr.strip.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "MCP runtime-authority declaration tests passed."
