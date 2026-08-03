# frozen_string_literal: true

require "json"
require "minitest/autorun"
require "net/http"
require "open3"
require "rbconfig"
require "socket"
require "timeout"
require "tmpdir"

class TextStatsMcpSystemdHttpServerTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  SERVER = File.join(ROOT, "mcp/http_server.rb")
  HOST = "127.0.0.1"
  TOKEN = "fixture-systemd-token-0123456789abcdef"
  ACCEPT = "application/json, text/event-stream"

  def free_port
    socket = TCPServer.new(HOST, 0)
    socket.addr.fetch(1)
  ensure
    socket&.close
  end

  def token_file(directory, name = "token")
    path = File.join(directory, name)
    File.binwrite(path, "#{TOKEN}\n")
    File.chmod(0o600, path)
    path
  end

  def start_server(environment)
    stdin, stdout, stderr, wait = Open3.popen3(environment, RbConfig.ruby, SERVER, chdir: ROOT)
    stdin.close
    [stdout, stderr, wait]
  end

  def request(port, request)
    http = Net::HTTP.new(HOST, port, nil)
    http.open_timeout = 2
    http.read_timeout = 2
    http.start { |connection| connection.request(request) }
  end

  def wait_ready(port)
    Timeout.timeout(6) do
      loop do
        begin
          response = request(port, Net::HTTP::Get.new("/readyz"))
          return if response.code == "200"
        rescue IOError, SystemCallError
          nil
        end
        sleep 0.05
      end
    end
  end

  def stop(wait, stdout, stderr)
    Process.kill("TERM", wait.pid) if wait.alive?
    status = Timeout.timeout(4) { wait.value }
    [status, stdout.read, stderr.read]
  ensure
    stdout.close unless stdout.closed?
    stderr.close unless stderr.closed?
  end

  def initialize_session(port)
    request_object = Net::HTTP::Post.new("/mcp")
    request_object["Accept"] = ACCEPT
    request_object["Content-Type"] = "application/json"
    request_object["Authorization"] = "Bearer #{TOKEN}"
    request_object.body = JSON.generate(
      jsonrpc: "2.0",
      method: "initialize",
      id: 1,
      params: {
        protocolVersion: "2025-11-25",
        capabilities: {},
        clientInfo: { name: "systemd-fixture-test", version: "1.0.0" }
      }
    )
    response = request(port, request_object)
    assert_equal "200", response.code
    [response["mcp-session-id"], JSON.parse(response.body)]
  end

  def test_file_backed_http_contract
    Dir.mktmpdir("mcp-systemd-http") do |directory|
      port = free_port
      token = token_file(directory)
      stdout, stderr, wait = start_server(
        "TEXT_STATS_MCP_HTTP_TOKEN_FILE" => token,
        "TEXT_STATS_MCP_HTTP_PORT" => port.to_s
      )
      wait_ready(port)

      readiness = request(port, Net::HTTP::Get.new("/readyz"))
      assert_equal({ "status" => "ready" }, JSON.parse(readiness.body))

      unauthorized_request = Net::HTTP::Post.new("/mcp")
      unauthorized_request["Accept"] = ACCEPT
      unauthorized_request["Content-Type"] = "application/json"
      unauthorized_request.body = "{}"
      assert_equal "401", request(port, unauthorized_request).code

      session_id, initialization = initialize_session(port)
      assert_equal "2025-11-25", initialization.fetch("result").fetch("protocolVersion")
      refute_nil session_id

      notify = Net::HTTP::Post.new("/mcp")
      notify["Accept"] = ACCEPT
      notify["Content-Type"] = "application/json"
      notify["Authorization"] = "Bearer #{TOKEN}"
      notify["Mcp-Session-Id"] = session_id
      notify["MCP-Protocol-Version"] = "2025-11-25"
      notify.body = JSON.generate(jsonrpc: "2.0", method: "notifications/initialized", params: {})
      assert_equal "202", request(port, notify).code

      inventory = Net::HTTP::Post.new("/mcp")
      inventory["Accept"] = ACCEPT
      inventory["Content-Type"] = "application/json"
      inventory["Authorization"] = "Bearer #{TOKEN}"
      inventory["Mcp-Session-Id"] = session_id
      inventory["MCP-Protocol-Version"] = "2025-11-25"
      inventory.body = JSON.generate(jsonrpc: "2.0", method: "tools/list", id: 2, params: {})
      tools = JSON.parse(request(port, inventory).body).fetch("result").fetch("tools")
      assert_equal ["text_stats"], tools.map { |tool| tool.fetch("name") }

      [[3, "alpha beta\n", { "bytes" => 11, "lines" => 1, "words" => 2 }],
       [4, "gamma\ndelta\n", { "bytes" => 12, "lines" => 2, "words" => 2 }]].each do |id, text, expected|
        call = Net::HTTP::Post.new("/mcp")
        call["Accept"] = ACCEPT
        call["Content-Type"] = "application/json"
        call["Authorization"] = "Bearer #{TOKEN}"
        call["Mcp-Session-Id"] = session_id
        call["MCP-Protocol-Version"] = "2025-11-25"
        call.body = JSON.generate(
          jsonrpc: "2.0",
          method: "tools/call",
          id: id,
          params: { name: "text_stats", arguments: { text: text } }
        )
        result = JSON.parse(request(port, call).body).fetch("result").fetch("structuredContent")
        assert_equal expected, result
      end

      bad_origin = Net::HTTP::Get.new("/readyz")
      bad_origin["Origin"] = "https://evil.example"
      assert_equal "403", request(port, bad_origin).code

      status, output, diagnostics = stop(wait, stdout, stderr)
      assert status.success?
      assert_equal "", output
      refute_includes diagnostics, TOKEN
    end
  end

  def test_systemd_credential_and_ready_notification
    Dir.mktmpdir("mcp-systemd-credential") do |directory|
      token_file(directory, "text-stats-mcp-token")
      notify_path = File.join(directory, "notify.sock")
      notify_socket = Socket.new(Socket::AF_UNIX, Socket::SOCK_DGRAM, 0)
      notify_socket.bind(Socket.pack_sockaddr_un(notify_path))
      port = free_port
      stdout, stderr, wait = start_server(
        "CREDENTIALS_DIRECTORY" => directory,
        "NOTIFY_SOCKET" => notify_path,
        "TEXT_STATS_MCP_HTTP_PORT" => port.to_s
      )

      message = Timeout.timeout(6) { notify_socket.recv(4096) }
      assert_includes message, "READY=1"
      wait_ready(port)
      status, output, diagnostics = stop(wait, stdout, stderr)
      assert status.success?
      assert_equal "", output
      assert_includes diagnostics, "service ready"
    ensure
      notify_socket&.close
    end
  end

  def test_configuration_boundaries_fail_before_listener
    Dir.mktmpdir("mcp-systemd-config") do |directory|
      token = token_file(directory)
      port = free_port
      stdout, stderr, status = Open3.capture3(
        {
          "TEXT_STATS_MCP_HTTP_TOKEN_FILE" => token,
          "CREDENTIALS_DIRECTORY" => directory,
          "TEXT_STATS_MCP_HTTP_PORT" => port.to_s
        },
        RbConfig.ruby,
        SERVER,
        chdir: ROOT
      )
      refute status.success?
      assert_equal 78, status.exitstatus
      assert_equal "", stdout
      assert_includes stderr, "not both"

      stdout, stderr, status = Open3.capture3(
        {
          "TEXT_STATS_MCP_HTTP_TOKEN_FILE" => token,
          "TEXT_STATS_MCP_HTTP_BIND" => "0.0.0.0",
          "TEXT_STATS_MCP_HTTP_PORT" => port.to_s
        },
        RbConfig.ruby,
        SERVER,
        chdir: ROOT
      )
      refute status.success?
      assert_equal 78, status.exitstatus
      assert_equal "", stdout
      assert_includes stderr, "must be 127.0.0.1"
      refute_includes stderr, TOKEN
    end
  end
end
