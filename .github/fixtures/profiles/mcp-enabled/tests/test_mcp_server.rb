# frozen_string_literal: true

require "json"
require "minitest/autorun"
require "open3"
require "rbconfig"
require "timeout"
require_relative "../src/text_stats"

class TextStatsMcpServerTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  COMMAND = [RbConfig.ruby, File.join(ROOT, "mcp/server.rb")].freeze
  REQUEST_TIMEOUT = 2

  class StdioSession
    attr_reader :pid

    def initialize(timeout: REQUEST_TIMEOUT)
      @timeout = timeout
      @stdin, @stdout, @stderr, @wait_thread = Open3.popen3(*COMMAND, chdir: ROOT)
      @stdin.sync = true
      @closed = false
      @stdout_messages = []
    end

    def request(id, method, params = nil)
      payload = { jsonrpc: "2.0", id: id, method: method }
      payload[:params] = params unless params.nil?
      write(payload)
      read_response(id)
    end

    def notify(method, params = nil)
      payload = { jsonrpc: "2.0", method: method }
      payload[:params] = params unless params.nil?
      write(payload)
    end

    def close_gracefully
      @stdin.close unless @stdin.closed?
      status = wait_bounded
      remaining_stdout = @stdout.read
      diagnostics = @stderr.read
      @closed = true
      [status, remaining_stdout, diagnostics]
    ensure
      close_streams
    end

    def terminate_bounded
      terminate_process("TERM")
      status = wait_bounded(term_first: false)
      diagnostics = @stderr.read
      @closed = true
      [status, diagnostics]
    ensure
      close_streams
    end

    def abort_after_read_timeout
      Timeout.timeout(0.1) { @stdout.gets }
      raise "expected a read timeout"
    rescue Timeout::Error
      terminate_bounded
    end

    def alive?
      @wait_thread.alive?
    end

    private

    def write(payload)
      @stdin.puts(JSON.generate(payload))
      @stdin.flush
    end

    def read_response(expected_id)
      loop do
        line = Timeout.timeout(@timeout) { @stdout.gets }
        raise EOFError, "MCP server closed stdout before responding" if line.nil?

        message = JSON.parse(line)
        @stdout_messages << message
        return message if message["id"] == expected_id
      end
    end

    def wait_bounded(term_first: true)
      Timeout.timeout(@timeout) { return @wait_thread.value }
    rescue Timeout::Error
      terminate_process("TERM") if term_first
      begin
        Timeout.timeout(1) { return @wait_thread.value }
      rescue Timeout::Error
        terminate_process("KILL")
        return @wait_thread.value
      end
    end

    def terminate_process(signal)
      Process.kill(signal, @wait_thread.pid) if @wait_thread.alive?
    rescue Errno::ESRCH
      nil
    end

    def close_streams
      [@stdin, @stdout, @stderr].each do |stream|
        stream.close unless stream.closed?
      rescue IOError
        nil
      end
    end
  end

  def initialize_protocol(session, revision: TextStatsMcp::PROTOCOL_VERSION)
    response = session.request(
      1,
      "initialize",
      {
        protocolVersion: revision,
        capabilities: {},
        clientInfo: { name: "fixture-test-client", version: "1.0.0" }
      }
    )
    session.notify("notifications/initialized", {}) unless response.key?("error")
    response
  end

  def assert_json_rpc_error(response, code)
    assert_equal "2.0", response.fetch("jsonrpc")
    assert_equal code, response.fetch("error").fetch("code")
  end

  def test_initialization_and_tool_inventory
    session = StdioSession.new
    initialization = initialize_protocol(session)

    result = initialization.fetch("result")
    assert_equal TextStatsMcp::PROTOCOL_VERSION, result.fetch("protocolVersion")
    assert_equal ["tools"], result.fetch("capabilities").keys
    assert_equal "text_stats_fixture", result.fetch("serverInfo").fetch("name")

    inventory = session.request(2, "tools/list", {})
    tools_result = inventory.fetch("result")
    assert_equal [TextStatsMcp::TOOL_NAME], tools_result.fetch("tools").map { |tool| tool.fetch("name") }
    refute tools_result.key?("nextCursor")

    tool = tools_result.fetch("tools").first
    assert_equal ["text"], tool.fetch("inputSchema").fetch("required")
    assert_equal %w[bytes lines words], tool.fetch("outputSchema").fetch("required")
    assert_equal true, tool.fetch("annotations").fetch("readOnlyHint")
  ensure
    session&.close_gracefully
  end

  def test_successful_tool_call
    session = StdioSession.new
    initialize_protocol(session)

    response = session.request(
      2,
      "tools/call",
      { name: TextStatsMcp::TOOL_NAME, arguments: { text: "one two\n" } }
    )
    result = response.fetch("result")
    expected = { "bytes" => 8, "lines" => 1, "words" => 2 }

    assert_equal false, result.fetch("isError")
    assert_equal expected, result.fetch("structuredContent")
    assert_equal expected, JSON.parse(result.fetch("content").first.fetch("text"))
  ensure
    session&.close_gracefully
  end

  def test_validation_error_keeps_session_usable
    session = StdioSession.new
    initialize_protocol(session)

    invalid = session.request(
      2,
      "tools/call",
      { name: TextStatsMcp::TOOL_NAME, arguments: {} }
    )
    invalid_result = invalid.fetch("result")
    assert_equal true, invalid_result.fetch("isError")
    assert_match(/Missing required arguments: text/, invalid_result.fetch("content").first.fetch("text"))

    ping = session.request(3, "ping", {})
    assert_equal({}, ping.fetch("result"))
  ensure
    session&.close_gracefully
  end

  def test_unknown_method_returns_protocol_error_and_keeps_session_usable
    session = StdioSession.new
    initialize_protocol(session)

    error = session.request(2, "tools/show", { name: TextStatsMcp::TOOL_NAME })
    assert_json_rpc_error(error, -32_601)

    ping = session.request(3, "ping", {})
    assert_equal({}, ping.fetch("result"))
  ensure
    session&.close_gracefully
  end

  def test_rejects_unselected_protocol_revision_without_fallback
    session = StdioSession.new
    rejected = initialize_protocol(session, revision: "2025-06-18")
    assert_json_rpc_error(rejected, -32_602)

    accepted = initialize_protocol(session)
    assert_equal TextStatsMcp::PROTOCOL_VERSION, accepted.fetch("result").fetch("protocolVersion")
  ensure
    session&.close_gracefully
  end

  def test_sequential_tool_calls
    session = StdioSession.new
    initialize_protocol(session)

    first = session.request(
      2,
      "tools/call",
      { name: TextStatsMcp::TOOL_NAME, arguments: { text: "alpha" } }
    )
    second = session.request(
      3,
      "tools/call",
      { name: TextStatsMcp::TOOL_NAME, arguments: { text: "beta gamma\n" } }
    )

    assert_equal({ "bytes" => 5, "lines" => 1, "words" => 1 }, first.fetch("result").fetch("structuredContent"))
    assert_equal({ "bytes" => 11, "lines" => 1, "words" => 2 }, second.fetch("result").fetch("structuredContent"))
  ensure
    session&.close_gracefully
  end

  def test_graceful_shutdown_and_stream_separation
    session = StdioSession.new
    initialize_protocol(session)

    status, remaining_stdout, diagnostics = session.close_gracefully
    session = nil

    assert status.success?, "expected graceful exit, got #{status.inspect}"
    assert_equal "", remaining_stdout
    assert_equal(
      "text-stats MCP stdio server starting\ntext-stats MCP stdio server stopped\n",
      diagnostics
    )
  ensure
    session&.close_gracefully
  end

  def test_read_timeout_reaps_abnormal_child_without_hanging
    session = StdioSession.new(timeout: 0.5)
    started = Process.clock_gettime(Process::CLOCK_MONOTONIC)

    status, diagnostics = session.abort_after_read_timeout
    session = nil
    elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - started

    refute status.success?
    assert_operator elapsed, :<, 2.0
    assert_includes diagnostics, "text-stats MCP stdio server starting"
  ensure
    session&.terminate_bounded
  end
end
