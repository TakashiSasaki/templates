# frozen_string_literal: true

require "json"
require "minitest/autorun"
require "open3"
require "rbconfig"
require "timeout"
require_relative "../src/text_stats"

class TextStatInterfaceEquivalenceTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  CLI_COMMAND = [RbConfig.ruby, File.join(ROOT, "bin/text-stat")].freeze
  MCP_COMMAND = [RbConfig.ruby, File.join(ROOT, "mcp/server.rb")].freeze
  TIMEOUT = 2

  def test_actual_cli_and_mcp_results_match_shared_domain_operation
    text = "alpha βeta\ngamma\n"
    cli_stdout, cli_stderr, cli_status = Open3.capture3(
      *CLI_COMMAND,
      "--output",
      "json",
      "-",
      stdin_data: text,
      chdir: ROOT
    )
    assert cli_status.success?, cli_stderr
    cli_result = JSON.parse(cli_stdout).fetch("result")

    stdin, stdout, stderr, wait_thread = Open3.popen3(*MCP_COMMAND, chdir: ROOT)
    stdin.sync = true
    write_message(
      stdin,
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: TextStatsMcp::PROTOCOL_VERSION,
        capabilities: {},
        clientInfo: { name: "equivalence-test", version: "1.0.0" }
      }
    )
    initialization = read_response(stdout, 1)
    assert_equal TextStatsMcp::PROTOCOL_VERSION, initialization.fetch("result").fetch("protocolVersion")

    write_message(stdin, jsonrpc: "2.0", method: "notifications/initialized", params: {})
    write_message(
      stdin,
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: { name: TextStatsMcp::TOOL_NAME, arguments: { text: text } }
    )
    mcp_result = read_response(stdout, 2).fetch("result")

    assert_equal false, mcp_result.fetch("isError")
    assert_equal TextStat.analyze(text), cli_result
    assert_equal cli_result, mcp_result.fetch("structuredContent")
    assert_equal cli_result, JSON.parse(mcp_result.fetch("content").first.fetch("text"))
  ensure
    stdin&.close unless stdin&.closed?
    status = wait_for_bounded_exit(wait_thread) if wait_thread
    diagnostics = stderr&.read.to_s
    assert status.success?, diagnostics if status
    [stdout, stderr].compact.each do |stream|
      stream.close unless stream.closed?
    rescue IOError
      nil
    end
  end

  private

  def write_message(stream, payload)
    stream.puts(JSON.generate(payload))
    stream.flush
  end

  def read_response(stream, expected_id)
    loop do
      line = Timeout.timeout(TIMEOUT) { stream.gets }
      raise EOFError, "MCP server closed stdout before responding" if line.nil?

      response = JSON.parse(line)
      return response if response["id"] == expected_id
    end
  end

  def wait_for_bounded_exit(wait_thread)
    Timeout.timeout(TIMEOUT) { return wait_thread.value }
  rescue Timeout::Error
    signal(wait_thread, "TERM")
    begin
      Timeout.timeout(1) { return wait_thread.value }
    rescue Timeout::Error
      signal(wait_thread, "KILL")
      wait_thread.value
    end
  end

  def signal(wait_thread, name)
    Process.kill(name, wait_thread.pid) if wait_thread.alive?
  rescue Errno::ESRCH
    nil
  end
end
