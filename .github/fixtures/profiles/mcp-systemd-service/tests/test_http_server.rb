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
  MAX_REQUEST_BYTES = 65_536
  MAX_SESSIONS = 16

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

  def build_http(port)
    http = Net::HTTP.new(HOST, port, nil)
    http.open_timeout = 2
    http.read_timeout = 2
    http.write_timeout = 2 if http.respond_to?(:write_timeout=)
    http
  end

  def request(port, request)
    build_http(port).start { |connection| connection.request(request) }
  end

  def raw_http_status(port, request_bytes)
    socket = TCPSocket.new(HOST, port)
    socket.write(request_bytes)
    Timeout.timeout(3) { socket.gets.to_s }
  ensure
    socket&.close
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

  def initialize_params(revision: "2025-11-25")
    {
      protocolVersion: revision,
      capabilities: {},
      clientInfo: { name: "systemd-fixture-test", version: "1.0.0" }
    }
  end

  def initialize_request(params, id: 1)
    request_object = Net::HTTP::Post.new("/mcp")
    request_object["Accept"] = ACCEPT
    request_object["Content-Type"] = "application/json"
    request_object["Authorization"] = "Bearer #{TOKEN}"
    request_object.body = JSON.generate(jsonrpc: "2.0", method: "initialize", id: id, params: params)
    request_object
  end

  def delete_session_request(session_id)
    request_object = Net::HTTP::Delete.new("/mcp")
    request_object["Authorization"] = "Bearer #{TOKEN}"
    request_object["Mcp-Session-Id"] = session_id
    request_object["MCP-Protocol-Version"] = "2025-11-25"
    request_object
  end

  def initialize_session(connection, id: 1)
    response = connection.request(initialize_request(initialize_params, id: id))
    assert_equal "200", response.code
    result = JSON.parse(response.body).fetch("result")
    assert_equal "2025-11-25", result.fetch("protocolVersion")
    session_id = response["mcp-session-id"]
    refute_nil session_id
    refute_empty session_id
    [session_id, result]
  end

  def assert_invalid_initialize(response)
    assert_equal "200", response.code
    payload = JSON.parse(response.body)
    assert_equal "2.0", payload.fetch("jsonrpc")
    assert_equal(-32_602, payload.fetch("error").fetch("code"))
    assert_nil response["mcp-session-id"]
  end

  def test_file_backed_http_contract_and_reused_connection_policy
    Dir.mktmpdir("mcp-systemd-http") do |directory|
      port = free_port
      token = token_file(directory)
      stdout, stderr, wait = start_server(
        "TEXT_STATS_MCP_HTTP_TOKEN_FILE" => token,
        "TEXT_STATS_MCP_HTTP_PORT" => port.to_s
      )
      wait_ready(port)

      build_http(port).start do |connection|
        readiness = connection.request(Net::HTTP::Get.new("/readyz"))
        assert_equal({ "status" => "ready" }, JSON.parse(readiness.body))

        session_id, = initialize_session(connection)

        notify = Net::HTTP::Post.new("/mcp")
        notify["Accept"] = ACCEPT
        notify["Content-Type"] = "application/json"
        notify["Authorization"] = "Bearer #{TOKEN}"
        notify["Mcp-Session-Id"] = session_id
        notify["MCP-Protocol-Version"] = "2025-11-25"
        notify.body = JSON.generate(jsonrpc: "2.0", method: "notifications/initialized", params: {})
        assert_equal "202", connection.request(notify).code

        inventory = Net::HTTP::Post.new("/mcp")
        inventory["Accept"] = ACCEPT
        inventory["Content-Type"] = "application/json"
        inventory["Authorization"] = "Bearer #{TOKEN}"
        inventory["Mcp-Session-Id"] = session_id
        inventory["MCP-Protocol-Version"] = "2025-11-25"
        inventory.body = JSON.generate(jsonrpc: "2.0", method: "tools/list", id: 2, params: {})
        tools = JSON.parse(connection.request(inventory).body).fetch("result").fetch("tools")
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
          result = JSON.parse(connection.request(call).body).fetch("result").fetch("structuredContent")
          assert_equal expected, result
        end

        bad_origin = Net::HTTP::Get.new("/readyz")
        bad_origin["Origin"] = "https://evil.example"
        assert_equal "403", connection.request(bad_origin).code

        missing_auth = Net::HTTP::Post.new("/mcp")
        missing_auth["Accept"] = ACCEPT
        missing_auth["Content-Type"] = "application/json"
        missing_auth["Mcp-Session-Id"] = session_id
        missing_auth["MCP-Protocol-Version"] = "2025-11-25"
        missing_auth.body = JSON.generate(jsonrpc: "2.0", method: "ping", id: 5, params: {})
        assert_equal "401", connection.request(missing_auth).code

        bad_host = Net::HTTP::Get.new("/readyz")
        bad_host["Host"] = "evil.example"
        assert_equal "403", connection.request(bad_host).code

        valid_again = connection.request(Net::HTTP::Get.new("/readyz"))
        assert_equal "200", valid_again.code
        assert_equal({ "status" => "ready" }, JSON.parse(valid_again.body))
      end

      status, output, diagnostics = stop(wait, stdout, stderr)
      assert status.success?
      assert_equal "", output
      refute_includes diagnostics, TOKEN
    end
  end

  def test_initialization_negotiation_and_validation_outcomes
    Dir.mktmpdir("mcp-systemd-initialize") do |directory|
      port = free_port
      token = token_file(directory)
      stdout, stderr, wait = start_server(
        "TEXT_STATS_MCP_HTTP_TOKEN_FILE" => token,
        "TEXT_STATS_MCP_HTTP_PORT" => port.to_s
      )
      wait_ready(port)

      build_http(port).start do |connection|
        negotiated = connection.request(
          initialize_request(initialize_params(revision: "2025-06-18"), id: 10)
        )
        assert_equal "200", negotiated.code
        assert_equal "2025-11-25", JSON.parse(negotiated.body).fetch("result").fetch("protocolVersion")
        refute_empty negotiated["mcp-session-id"].to_s

        missing_revision = initialize_params.reject { |key, _value| key == :protocolVersion }
        assert_invalid_initialize(connection.request(initialize_request(missing_revision, id: 11)))

        non_string_revision = initialize_params(revision: 20_251_125)
        assert_invalid_initialize(connection.request(initialize_request(non_string_revision, id: 12)))
      end

      status, output, diagnostics = stop(wait, stdout, stderr)
      assert status.success?
      assert_equal "", output
      refute_includes diagnostics, TOKEN
    end
  end

  def test_session_capacity_delete_and_recovery
    Dir.mktmpdir("mcp-systemd-capacity") do |directory|
      port = free_port
      token = token_file(directory)
      stdout, stderr, wait = start_server(
        "TEXT_STATS_MCP_HTTP_TOKEN_FILE" => token,
        "TEXT_STATS_MCP_HTTP_PORT" => port.to_s
      )
      wait_ready(port)

      build_http(port).start do |connection|
        session_ids = Array.new(MAX_SESSIONS) do |index|
          initialize_session(connection, id: 100 + index).first
        end

        rejected = connection.request(initialize_request(initialize_params, id: 200))
        assert_equal "503", rejected.code
        assert_nil rejected["mcp-session-id"]

        deleted = connection.request(delete_session_request(session_ids.shift))
        assert_equal "200", deleted.code

        replacement = connection.request(initialize_request(initialize_params, id: 201))
        assert_equal "200", replacement.code
        refute_empty replacement["mcp-session-id"].to_s
      end

      status, output, diagnostics = stop(wait, stdout, stderr)
      assert status.success?
      assert_equal "", output
      refute_includes diagnostics, TOKEN
    end
  end

  def test_server_read_boundary_rejects_declared_and_chunked_oversize_bodies
    Dir.mktmpdir("mcp-systemd-body-limit") do |directory|
      port = free_port
      token = token_file(directory)
      stdout, stderr, wait = start_server(
        "TEXT_STATS_MCP_HTTP_TOKEN_FILE" => token,
        "TEXT_STATS_MCP_HTTP_PORT" => port.to_s
      )
      wait_ready(port)

      declared = [
        "POST /mcp HTTP/1.1",
        "Host: #{HOST}:#{port}",
        "Accept: #{ACCEPT}",
        "Content-Type: application/json",
        "Authorization: Bearer #{TOKEN}",
        "Content-Length: #{MAX_REQUEST_BYTES + 1}",
        "Connection: close",
        "",
        ""
      ].join("\r\n")
      assert_match(/\AHTTP\/1\.1 413\b/, raw_http_status(port, declared))

      chunk_size = MAX_REQUEST_BYTES + 1
      chunked = [
        "POST /mcp HTTP/1.1",
        "Host: #{HOST}:#{port}",
        "Accept: #{ACCEPT}",
        "Content-Type: application/json",
        "Authorization: Bearer #{TOKEN}",
        "Transfer-Encoding: chunked",
        "Connection: close",
        "",
        "#{chunk_size.to_s(16)}\r\n#{"x" * chunk_size}\r\n0\r\n\r\n"
      ].join("\r\n")
      assert_match(/\AHTTP\/1\.1 413\b/, raw_http_status(port, chunked))

      readiness = request(port, Net::HTTP::Get.new("/readyz"))
      assert_equal "200", readiness.code

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
