# frozen_string_literal: true

require "json"
require "minitest/autorun"
require "net/http"
require "open3"
require "rbconfig"
require "socket"
require "timeout"
require_relative "../src/text_stats"

class TextStatsMcpHttpServerTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  HTTP_SERVER = File.join(ROOT, "mcp/http_server.rb")
  STDIO_SERVER = File.join(ROOT, "mcp/server.rb")
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

    def initialize(port: self.class.free_port, token: TOKEN, bind: HOST)
      @port = port
      environment = {
        "TEXT_STATS_MCP_HTTP_BIND" => bind,
        "TEXT_STATS_MCP_HTTP_PORT" => port.to_s,
        "TEXT_STATS_MCP_HTTP_TOKEN" => token
      }
      @stdin, @stdout, @stderr, @wait_thread = Open3.popen3(
        environment,
        RbConfig.ruby,
        HTTP_SERVER,
        chdir: ROOT
      )
      @stdin.close
      @stopped = false
      wait_until_ready
    end

    def authority
      "#{HOST}:#{port}"
    end

    def origin
      "http://#{authority}"
    end

    def with_http
      http = Net::HTTP.new(HOST, port, nil)
      http.open_timeout = REQUEST_TIMEOUT
      http.read_timeout = REQUEST_TIMEOUT
      http.write_timeout = REQUEST_TIMEOUT if http.respond_to?(:write_timeout=)
      http.start { yield http }
    end

    def request(request, http: nil)
      return http.request(request) if http

      with_http { |connection| connection.request(request) }
    end

    def get(path, origin: nil, host: nil, http: nil)
      request = Net::HTTP::Get.new(path)
      request["Host"] = host if host
      request["Origin"] = origin if origin
      self.request(request, http: http)
    end

    def post_json(payload, session_id: nil, token: TOKEN, origin: nil, host: nil,
                  protocol_version: nil, raw_body: nil, http: nil)
      request = Net::HTTP::Post.new("/mcp")
      request["Accept"] = "application/json"
      request["Content-Type"] = "application/json"
      request["Authorization"] = "Bearer #{token}" if token
      request["Mcp-Session-Id"] = session_id if session_id
      request["MCP-Protocol-Version"] = protocol_version if protocol_version
      request["Origin"] = origin if origin
      request["Host"] = host if host
      request.body = raw_body || JSON.generate(payload)
      self.request(request, http: http)
    end

    def delete_session(session_id, token: TOKEN, origin: nil, http: nil)
      request = Net::HTTP::Delete.new("/mcp")
      request["Authorization"] = "Bearer #{token}"
      request["Mcp-Session-Id"] = session_id
      request["MCP-Protocol-Version"] = TextStatsMcp::PROTOCOL_VERSION
      request["Origin"] = origin if origin
      self.request(request, http: http)
    end

    def stop
      return [@status, @stdout_data, @stderr_data] if @stopped

      if @wait_thread.alive?
        begin
          Process.kill("TERM", @wait_thread.pid)
        rescue Errno::ESRCH
          nil
        end
      end

      @status = wait_bounded
      @stdout_data = @stdout.read
      @stderr_data = @stderr.read
      @stopped = true
      [@status, @stdout_data, @stderr_data]
    ensure
      close_streams if @stopped
    end

    private

    def wait_until_ready
      deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + 5
      loop do
        unless @wait_thread.alive?
          status = @wait_thread.value
          diagnostics = @stderr.read
          raise "HTTP server exited before readiness: #{status.inspect}; #{diagnostics.inspect}"
        end

        begin
          response = get("/readyz")
          return if response.code == "200"
        rescue IOError, SystemCallError, Timeout::Error
          nil
        end

        raise "HTTP server readiness timed out" if Process.clock_gettime(Process::CLOCK_MONOTONIC) >= deadline

        sleep 0.05
      end
    end

    def wait_bounded
      Timeout.timeout(3) { @wait_thread.value }
    rescue Timeout::Error
      begin
        Process.kill("KILL", @wait_thread.pid)
      rescue Errno::ESRCH
        nil
      end
      @wait_thread.value
    end

    def close_streams
      [@stdout, @stderr].each do |stream|
        stream.close unless stream.closed?
      rescue IOError
        nil
      end
    end
  end

  def initialize_params
    {
      protocolVersion: TextStatsMcp::PROTOCOL_VERSION,
      capabilities: {},
      clientInfo: { name: "fixture-http-test-client", version: "1.0.0" }
    }
  end

  def initialize_session(server, http: nil, origin: nil, token: TOKEN)
    response = server.post_json(
      { jsonrpc: "2.0", method: "initialize", id: 1, params: initialize_params },
      token: token,
      origin: origin,
      http: http
    )
    assert_equal "200", response.code
    result = JSON.parse(response.body).fetch("result")
    assert_equal TextStatsMcp::PROTOCOL_VERSION, result.fetch("protocolVersion")
    session_id = response["mcp-session-id"]
    refute_nil session_id
    refute_empty session_id
    session_id
  end

  def notify_initialized(server, session_id, http: nil, origin: nil, token: TOKEN)
    response = server.post_json(
      { jsonrpc: "2.0", method: "notifications/initialized", params: {} },
      session_id: session_id,
      token: token,
      origin: origin,
      protocol_version: TextStatsMcp::PROTOCOL_VERSION,
      http: http
    )
    assert_equal "202", response.code
  end

  def mcp_request(server, session_id, id:, method:, params: {}, http: nil, origin: nil,
                  token: TOKEN, protocol_version: TextStatsMcp::PROTOCOL_VERSION)
    server.post_json(
      { jsonrpc: "2.0", method: method, id: id, params: params },
      session_id: session_id,
      token: token,
      origin: origin,
      protocol_version: protocol_version,
      http: http
    )
  end

  def stdio_tool_call(text)
    stdin, stdout, stderr, wait_thread = Open3.popen3(RbConfig.ruby, STDIO_SERVER, chdir: ROOT)
    stdin.sync = true
    startup = Timeout.timeout(REQUEST_TIMEOUT) { stderr.gets }
    raise "stdio server closed before startup" if startup.nil?

    stdin.puts(JSON.generate(jsonrpc: "2.0", method: "initialize", id: 1, params: initialize_params))
    initialization = JSON.parse(Timeout.timeout(REQUEST_TIMEOUT) { stdout.gets })
    raise "stdio initialization failed" if initialization.key?("error")

    stdin.puts(JSON.generate(jsonrpc: "2.0", method: "notifications/initialized", params: {}))
    stdin.puts(
      JSON.generate(
        jsonrpc: "2.0",
        method: "tools/call",
        id: 2,
        params: { name: TextStatsMcp::TOOL_NAME, arguments: { text: text } }
      )
    )
    response = JSON.parse(Timeout.timeout(REQUEST_TIMEOUT) { stdout.gets })
    stdin.close
    Timeout.timeout(REQUEST_TIMEOUT) { wait_thread.value }
    response.fetch("result")
  ensure
    [stdin, stdout, stderr].compact.each do |stream|
      stream.close unless stream.closed?
    rescue IOError
      nil
    end
    if wait_thread&.alive?
      Process.kill("KILL", wait_thread.pid)
      wait_thread.value
    end
  end

  def run_configuration_failure(environment)
    Timeout.timeout(5) do
      Open3.capture3(environment, RbConfig.ruby, HTTP_SERVER, chdir: ROOT)
    end
  end

  def test_http_inventory_calls_and_stdio_equivalence
    server = HttpServerProcess.new
    session_id = initialize_session(server)
    notify_initialized(server, session_id)

    inventory_response = mcp_request(server, session_id, id: 2, method: "tools/list")
    assert_equal "200", inventory_response.code
    inventory = JSON.parse(inventory_response.body).fetch("result")
    assert_equal [TextStatsMcp::TOOL_NAME], inventory.fetch("tools").map { |tool| tool.fetch("name") }

    text = "alpha beta\n"
    http_response = mcp_request(
      server,
      session_id,
      id: 3,
      method: "tools/call",
      params: { name: TextStatsMcp::TOOL_NAME, arguments: { text: text } }
    )
    assert_equal "200", http_response.code
    http_result = JSON.parse(http_response.body).fetch("result")
    stdio_result = stdio_tool_call(text)

    assert_equal false, http_result.fetch("isError")
    assert_equal stdio_result.fetch("structuredContent"), http_result.fetch("structuredContent")
    assert_equal TextStatsMcp.analyze(text), http_result.fetch("structuredContent")
  ensure
    server&.stop
  end

  def test_request_scoped_host_origin_and_authentication_on_reused_connection
    server = HttpServerProcess.new
    server.with_http do |http|
      session_id = initialize_session(server, http: http)
      notify_initialized(server, session_id, http: http)

      bad_origin = mcp_request(
        server,
        session_id,
        id: 2,
        method: "ping",
        origin: "https://evil.example",
        http: http
      )
      assert_equal "403", bad_origin.code

      bad_token = mcp_request(
        server,
        session_id,
        id: 3,
        method: "ping",
        token: "x" * TOKEN.bytesize,
        http: http
      )
      assert_equal "401", bad_token.code

      request = Net::HTTP::Post.new("/mcp")
      request["Accept"] = "application/json"
      request["Content-Type"] = "application/json"
      request["Authorization"] = "Bearer #{TOKEN}"
      request["Mcp-Session-Id"] = session_id
      request["MCP-Protocol-Version"] = TextStatsMcp::PROTOCOL_VERSION
      request["Host"] = "evil.example"
      request.body = JSON.generate(jsonrpc: "2.0", method: "ping", id: 4, params: {})
      bad_host = server.request(request, http: http)
      assert_equal "403", bad_host.code

      valid = mcp_request(
        server,
        session_id,
        id: 5,
        method: "ping",
        origin: server.origin,
        http: http
      )
      assert_equal "200", valid.code
      assert_equal({}, JSON.parse(valid.body).fetch("result"))
    end
  ensure
    server&.stop
  end

  def test_limits_errors_and_readiness_are_isolated
    server = HttpServerProcess.new

    unauthorized = server.post_json(
      { jsonrpc: "2.0", method: "initialize", id: 1, params: initialize_params },
      token: nil
    )
    assert_equal "401", unauthorized.code

    oversized = server.post_json({}, raw_body: "x" * 65_537)
    assert_equal "413", oversized.code

    session_id = initialize_session(server)
    notify_initialized(server, session_id)

    invalid_tool = mcp_request(
      server,
      session_id,
      id: 2,
      method: "tools/call",
      params: { name: TextStatsMcp::TOOL_NAME, arguments: {} }
    )
    assert_equal "200", invalid_tool.code
    assert_equal true, JSON.parse(invalid_tool.body).fetch("result").fetch("isError")

    invalid_revision = mcp_request(
      server,
      session_id,
      id: 3,
      method: "ping",
      protocol_version: "1900-01-01"
    )
    assert_equal "400", invalid_revision.code

    readiness = server.get("/readyz")
    assert_equal "200", readiness.code
    assert_equal({ "status" => "ready" }, JSON.parse(readiness.body))

    bad_readiness_origin = server.get("/readyz", origin: "https://evil.example")
    assert_equal "403", bad_readiness_origin.code
  ensure
    server&.stop
  end

  def test_session_cap_delete_and_recovery
    server = HttpServerProcess.new
    session_ids = Array.new(16) { initialize_session(server) }

    rejected = server.post_json(
      { jsonrpc: "2.0", method: "initialize", id: 100, params: initialize_params }
    )
    assert_equal "503", rejected.code

    deleted = server.delete_session(session_ids.shift)
    assert_equal "200", deleted.code

    replacement = server.post_json(
      { jsonrpc: "2.0", method: "initialize", id: 101, params: initialize_params }
    )
    assert_equal "200", replacement.code
  ensure
    server&.stop
  end

  def test_graceful_shutdown_and_restart
    port = HttpServerProcess.free_port
    first = HttpServerProcess.new(port: port)
    status, stdout, diagnostics = first.stop
    first = nil

    assert status.success?, "expected graceful HTTP server exit, got #{status.inspect}"
    assert_equal "", stdout
    assert_includes diagnostics, "text-stats MCP HTTP server ready"
    assert_includes diagnostics, "text-stats MCP HTTP server stopped"

    second = HttpServerProcess.new(port: port)
    readiness = second.get("/readyz")
    assert_equal "200", readiness.code
    second_status, second_stdout, = second.stop
    second = nil

    assert second_status.success?
    assert_equal "", second_stdout
  ensure
    first&.stop
    second&.stop
  end

  def test_configuration_failures_are_prompt_and_do_not_echo_tokens
    secret = "s" * 40
    stdout, stderr, status = run_configuration_failure(
      "TEXT_STATS_MCP_HTTP_TOKEN" => nil,
      "TEXT_STATS_MCP_HTTP_PORT" => "4570",
      "TEXT_STATS_MCP_HTTP_BIND" => HOST
    )
    refute status.success?
    assert_equal "", stdout
    assert_includes stderr, "TEXT_STATS_MCP_HTTP_TOKEN"

    stdout, stderr, status = run_configuration_failure(
      "TEXT_STATS_MCP_HTTP_TOKEN" => secret,
      "TEXT_STATS_MCP_HTTP_PORT" => "4570",
      "TEXT_STATS_MCP_HTTP_BIND" => "0.0.0.0"
    )
    refute status.success?
    assert_equal "", stdout
    assert_includes stderr, "must be 127.0.0.1"
    refute_includes stderr, secret

    stdout, stderr, status = run_configuration_failure(
      "TEXT_STATS_MCP_HTTP_TOKEN" => secret,
      "TEXT_STATS_MCP_HTTP_PORT" => "not-a-port",
      "TEXT_STATS_MCP_HTTP_BIND" => HOST
    )
    refute status.success?
    assert_equal "", stdout
    assert_includes stderr, "base-10 integer"
    refute_includes stderr, secret
  end
end
