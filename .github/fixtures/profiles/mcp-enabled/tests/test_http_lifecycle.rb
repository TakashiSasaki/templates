# frozen_string_literal: true

require "json"
require "minitest/autorun"
require "net/http"
require "open3"
require "rbconfig"
require "socket"
require "timeout"
require "tmpdir"
require_relative "../src/text_stats"

class TextStatsMcpHttpLifecycleTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  HTTP_SERVER = File.join(ROOT, "mcp/http_server.rb")
  HOST = "127.0.0.1"
  TOKEN = "fixture-http-token-0123456789abcdef"
  REQUEST_TIMEOUT = 2

  class HttpServerProcess
    attr_reader :port

    def self.free_port
      listener = TCPServer.new(HOST, 0)
      listener.addr.fetch(1)
    ensure
      listener&.close
    end

    def initialize(session_idle_timeout: 1, tool_delay: 0.5, tool_marker: nil)
      @port = self.class.free_port
      environment = {
        "TEXT_STATS_MCP_HTTP_BIND" => HOST,
        "TEXT_STATS_MCP_HTTP_PORT" => port.to_s,
        "TEXT_STATS_MCP_HTTP_TOKEN" => TOKEN,
        "TEXT_STATS_MCP_TEST_MODE" => "1",
        "TEXT_STATS_MCP_TEST_SESSION_IDLE_TIMEOUT" => session_idle_timeout.to_s,
        "TEXT_STATS_MCP_TEST_TOOL_DELAY" => tool_delay.to_s,
        "TEXT_STATS_MCP_TEST_TOOL_MARKER" => tool_marker
      }.compact
      @stdin, @stdout, @stderr, @wait_thread = Open3.popen3(
        environment,
        RbConfig.ruby,
        HTTP_SERVER,
        chdir: ROOT
      )
      @stdin.close
      wait_until_ready
    end

    def request(request)
      http = Net::HTTP.new(HOST, port, nil)
      http.open_timeout = REQUEST_TIMEOUT
      http.read_timeout = REQUEST_TIMEOUT
      http.write_timeout = REQUEST_TIMEOUT if http.respond_to?(:write_timeout=)
      http.start { |connection| connection.request(request) }
    end

    def initialize_session(id: 1)
      post_json(
        { jsonrpc: "2.0", method: "initialize", id: id, params: initialize_params }
      )
    end

    def post_json(payload, session_id: nil)
      request = Net::HTTP::Post.new("/mcp")
      request["Accept"] = "application/json"
      request["Content-Type"] = "application/json"
      request["Authorization"] = "Bearer #{TOKEN}"
      request["Mcp-Session-Id"] = session_id if session_id
      request["MCP-Protocol-Version"] = TextStatsMcp::PROTOCOL_VERSION if session_id
      request.body = JSON.generate(payload)
      self.request(request)
    end

    def delete_session(session_id)
      request = Net::HTTP::Delete.new("/mcp")
      request["Authorization"] = "Bearer #{TOKEN}"
      request["Mcp-Session-Id"] = session_id
      request["MCP-Protocol-Version"] = TextStatsMcp::PROTOCOL_VERSION
      self.request(request)
    end

    def start_tool_call(session_id)
      body = JSON.generate(
        jsonrpc: "2.0",
        method: "tools/call",
        id: 99,
        params: { name: TextStatsMcp::TOOL_NAME, arguments: { text: "disconnect me" } }
      )
      request = [
        "POST /mcp HTTP/1.1",
        "Host: #{HOST}:#{port}",
        "Accept: application/json",
        "Content-Type: application/json",
        "Authorization: Bearer #{TOKEN}",
        "Mcp-Session-Id: #{session_id}",
        "MCP-Protocol-Version: #{TextStatsMcp::PROTOCOL_VERSION}",
        "Content-Length: #{body.bytesize}",
        "Connection: close",
        "",
        body
      ].join("\r\n")

      socket = TCPSocket.new(HOST, port)
      socket.write(request)
      socket
    end

    def stop
      return unless @wait_thread

      Process.kill("TERM", @wait_thread.pid) if @wait_thread.alive?
      Timeout.timeout(3) { @wait_thread.value }
    rescue Errno::ESRCH
      nil
    rescue Timeout::Error
      Process.kill("KILL", @wait_thread.pid) if @wait_thread.alive?
      @wait_thread.value
    ensure
      [@stdout, @stderr].compact.each do |stream|
        stream.close unless stream.closed?
      rescue IOError
        nil
      end
      @wait_thread = nil
    end

    private

    def initialize_params
      {
        protocolVersion: TextStatsMcp::PROTOCOL_VERSION,
        capabilities: {},
        clientInfo: { name: "fixture-lifecycle-test", version: "1.0.0" }
      }
    end

    def wait_until_ready
      deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + 5
      loop do
        raise "HTTP server exited before readiness" unless @wait_thread.alive?

        begin
          request = Net::HTTP::Get.new("/readyz")
          return if self.request(request).code == "200"
        rescue IOError, SystemCallError, Timeout::Error
          nil
        end

        raise "HTTP server readiness timed out" if Process.clock_gettime(Process::CLOCK_MONOTONIC) >= deadline

        sleep 0.05
      end
    end
  end

  def wait_for_marker(path, expected, timeout: 3)
    deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + timeout
    loop do
      return if File.file?(path) && File.binread(path) == "#{expected}\n"

      raise "tool marker did not reach #{expected.inspect}" if Process.clock_gettime(Process::CLOCK_MONOTONIC) >= deadline

      sleep 0.01
    end
  end

  def test_expired_sessions_restore_capacity_without_delete
    server = HttpServerProcess.new(session_idle_timeout: 1, tool_delay: 0)
    16.times do |index|
      response = server.initialize_session(id: index + 1)
      assert_equal "200", response.code
    end

    assert_equal "503", server.initialize_session(id: 100).code

    deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + 6
    replacement = nil
    loop do
      sleep 0.2
      replacement = server.initialize_session(id: 101)
      break if replacement.code == "200"
      assert_equal "503", replacement.code
      raise "expired sessions did not restore capacity" if Process.clock_gettime(Process::CLOCK_MONOTONIC) >= deadline
    end

    refute_empty replacement["mcp-session-id"].to_s
  ensure
    server&.stop
  end

  def test_disconnected_tool_request_completes_boundedly_and_leaves_session_usable
    Dir.mktmpdir("mcp-http-disconnect") do |directory|
      marker = File.join(directory, "tool-state")
      server = HttpServerProcess.new(session_idle_timeout: 10, tool_delay: 0.5, tool_marker: marker)
      initialization = server.initialize_session
      assert_equal "200", initialization.code
      session_id = initialization["mcp-session-id"]
      refute_empty session_id.to_s

      socket = server.start_tool_call(session_id)
      wait_for_marker(marker, "started")
      socket.close
      wait_for_marker(marker, "completed")

      ping = server.post_json(
        { jsonrpc: "2.0", method: "ping", id: 2, params: {} },
        session_id: session_id
      )
      assert_equal "200", ping.code
      assert_equal({}, JSON.parse(ping.body).fetch("result"))

      deleted = server.delete_session(session_id)
      assert_equal "200", deleted.code

      replacement = server.initialize_session(id: 3)
      assert_equal "200", replacement.code
    ensure
      socket&.close unless socket&.closed?
      server&.stop
    end
  end
end
