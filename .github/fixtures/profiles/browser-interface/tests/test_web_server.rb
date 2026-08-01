# frozen_string_literal: true

require "fileutils"
require "json"
require "minitest/autorun"
require "net/http"
require "open3"
require "rbconfig"
require "socket"
require "tempfile"
require "timeout"
require "tmpdir"
require "uri"
require_relative "../src/text_stats"

class TextStatsWebServerTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  COMMAND = [RbConfig.ruby, File.join(ROOT, "web/server.rb")].freeze
  WAIT_SECONDS = 5

  class ServerSession
    attr_reader :port, :base_url, :pid_file

    def initialize
      @temporary_directory = Dir.mktmpdir("text-stats-web-test")
      @pid_file = File.join(@temporary_directory, "server.pid")
      @env = {
        "TEXT_STATS_WEB_ENABLED" => "1",
        "TEXT_STATS_WEB_BIND" => "127.0.0.1",
        "TEXT_STATS_WEB_PORT" => "0",
        "TEXT_STATS_WEB_PID_FILE" => @pid_file,
        "RUBYOPT" => nil
      }
      @stdin, @stdout, @stderr, @wait_thread = Open3.popen3(@env, *COMMAND, chdir: ROOT)
      @stdin.close
      @diagnostics = +""
      ready = Timeout.timeout(WAIT_SECONDS) do
        loop do
          line = @stderr.gets
          raise EOFError, "Web server exited before readiness: #{@diagnostics}" if line.nil?

          @diagnostics << line
          match = line.match(%r{text-stats web ready http://127\.0\.0\.1:(\d+)/})
          break match if match
        end
      end
      @port = Integer(ready[1], 10)
      @base_url = "http://127.0.0.1:#{@port}"
      @command_env = @env.merge("TEXT_STATS_WEB_PORT" => @port.to_s)
      @closed = false
    end

    def request(method, path, body: nil, content_type: nil, host: nil, origin: nil)
      http = Net::HTTP.new("127.0.0.1", @port, nil, nil, nil, nil)
      request_class = {
        "GET" => Net::HTTP::Get,
        "POST" => Net::HTTP::Post,
        "PUT" => Net::HTTP::Put
      }.fetch(method)
      request = request_class.new(path)
      request["Host"] = host || "127.0.0.1:#{@port}"
      request["Origin"] = origin if origin
      request["Content-Type"] = content_type if content_type
      request.body = body unless body.nil?
      http.request(request)
    end

    def raw_chunked_post(path, chunks:, origin:)
      socket = TCPSocket.new("127.0.0.1", @port)
      body = chunks.map { |chunk| "#{chunk.bytesize.to_s(16)}\r\n#{chunk}\r\n" }.join + "0\r\n\r\n"
      request = <<~HTTP.gsub("\n", "\r\n")
        POST #{path} HTTP/1.1
        Host: 127.0.0.1:#{@port}
        Origin: #{origin}
        Content-Type: application/json
        Transfer-Encoding: chunked
        Connection: close
        
      HTTP
      socket.write(request + body)
      socket.close_write
      socket.read
    ensure
      socket&.close
    end

    def health_command
      Open3.capture3(@command_env, *COMMAND, "--health", chdir: ROOT)
    end

    def stop_command
      Open3.capture3(@command_env, *COMMAND, "--stop", chdir: ROOT)
    end

    def close
      return @final if @closed

      stop_stdout, stop_stderr, stop_status = stop_command
      status = wait_bounded
      @diagnostics << @stderr.read
      server_stdout = @stdout.read
      pid_file_removed = !File.exist?(@pid_file)
      @closed = true
      @final = {
        stop_stdout: stop_stdout,
        stop_stderr: stop_stderr,
        stop_status: stop_status,
        status: status,
        diagnostics: @diagnostics,
        server_stdout: server_stdout,
        pid_file_removed: pid_file_removed
      }
    ensure
      [@stdout, @stderr].each do |stream|
        stream.close unless stream.closed?
      rescue IOError
        nil
      end
      FileUtils.remove_entry(@temporary_directory) if @temporary_directory && File.exist?(@temporary_directory)
    end

    private

    def wait_bounded
      Timeout.timeout(WAIT_SECONDS) { return @wait_thread.value }
    rescue Timeout::Error
      Process.kill("KILL", @wait_thread.pid) if @wait_thread.alive?
      @wait_thread.value
    end
  end

  def json(response)
    JSON.parse(response.body)
  end

  def assert_security_headers(response)
    assert_equal "no-store", response["cache-control"]
    assert_includes response["content-security-policy"], "default-src 'none'"
    assert_equal "no-referrer", response["referrer-policy"]
    assert_equal "nosniff", response["x-content-type-options"]
    assert_equal "DENY", response["x-frame-options"]
  end

  def test_disabled_by_default_and_non_loopback_bind_rejection
    stdout, stderr, status = Open3.capture3({ "RUBYOPT" => nil }, *COMMAND, chdir: ROOT)
    assert_equal 78, status.exitstatus
    assert_equal "", stdout
    assert_equal "Web UI is disabled; set TEXT_STATS_WEB_ENABLED=1 to start it\n", stderr

    stdout, stderr, status = Open3.capture3(
      {
        "TEXT_STATS_WEB_ENABLED" => "1",
        "TEXT_STATS_WEB_BIND" => "0.0.0.0",
        "RUBYOPT" => nil
      },
      *COMMAND,
      chdir: ROOT
    )
    assert_equal 78, status.exitstatus
    assert_equal "", stdout
    assert_equal "TEXT_STATS_WEB_BIND must be 127.0.0.1\n", stderr
  end

  def test_ui_assets_routing_and_security_headers
    session = ServerSession.new

    root = session.request("GET", "/")
    assert_equal "200", root.code
    assert_includes root.body, "Text statistics verification"
    refute_includes root.body, "<script>"
    assert_security_headers(root)

    script = session.request("GET", "/app.js")
    assert_equal "200", script.code
    assert_includes script["content-type"], "text/javascript"
    assert_includes script.body, "/api/text-stats"

    stylesheet = session.request("GET", "/app.css")
    assert_equal "200", stylesheet.code
    assert_includes stylesheet["content-type"], "text/css"

    missing = session.request("GET", "/missing")
    assert_equal "404", missing.code
    assert_equal({ "ok" => false, "error" => "not found" }, json(missing))

    wrong_method = session.request("PUT", "/healthz")
    assert_equal "405", wrong_method.code
    assert_equal "GET", wrong_method["allow"]

    forbidden_host = session.request("GET", "/healthz", host: "example.test")
    assert_equal "403", forbidden_host.code
    assert_equal "forbidden host", json(forbidden_host).fetch("error")
  ensure
    session&.close
  end

  def test_successful_api_result_is_versioned_and_does_not_echo_input
    session = ServerSession.new
    secret_text = "alpha secret-token\n"
    response = session.request(
      "POST",
      "/api/text-stats",
      body: JSON.generate("text" => secret_text),
      content_type: "application/json",
      origin: session.base_url
    )

    assert_equal "200", response.code
    assert_security_headers(response)
    assert_equal(
      {
        "contractVersion" => "1",
        "ok" => true,
        "result" => { "bytes" => 19, "lines" => 1, "words" => 2 }
      },
      json(response)
    )
    refute_includes response.body, "secret-token"

    final = session.close
    session = nil
    assert final.fetch(:status).success?
    assert_equal "", final.fetch(:server_stdout)
    refute_includes final.fetch(:diagnostics), "secret-token"
  ensure
    session&.close
  end

  def test_origin_content_type_schema_encoding_and_size_failures_preserve_health
    session = ServerSession.new
    valid_body = JSON.generate("text" => "one two")

    no_origin = session.request(
      "POST", "/api/text-stats", body: valid_body, content_type: "application/json"
    )
    assert_equal "403", no_origin.code

    cross_origin = session.request(
      "POST",
      "/api/text-stats",
      body: valid_body,
      content_type: "application/json",
      origin: "https://example.test"
    )
    assert_equal "403", cross_origin.code

    wrong_type = session.request(
      "POST",
      "/api/text-stats",
      body: valid_body,
      content_type: "text/plain",
      origin: session.base_url
    )
    assert_equal "415", wrong_type.code

    invalid_json = session.request(
      "POST",
      "/api/text-stats",
      body: "{",
      content_type: "application/json",
      origin: session.base_url
    )
    assert_equal "400", invalid_json.code

    invalid_schema = session.request(
      "POST",
      "/api/text-stats",
      body: JSON.generate("text" => "x", "extra" => true),
      content_type: "application/json",
      origin: session.base_url
    )
    assert_equal "422", invalid_schema.code

    invalid_utf8 = session.request(
      "POST",
      "/api/text-stats",
      body: "{\"text\":\"".b + [0xFF].pack("C") + "\"}".b,
      content_type: "application/json",
      origin: session.base_url
    )
    assert_equal "400", invalid_utf8.code

    oversized = session.request(
      "POST",
      "/api/text-stats",
      body: JSON.generate("text" => "x" * 65_536),
      content_type: "application/json",
      origin: session.base_url
    )
    assert_equal "413", oversized.code
    assert_equal "close", oversized["connection"]

    chunked = session.raw_chunked_post(
      "/api/text-stats",
      chunks: ["x" * 32_768, "x" * 32_768, "x"],
      origin: session.base_url
    )
    assert_match(/\AHTTP\/1\.[01] 413 /, chunked)

    health = session.request("GET", "/healthz")
    assert_equal "200", health.code
    assert_equal({ "ok" => true, "interface" => "web" }, json(health))
  ensure
    session&.close
  end

  def test_readiness_and_documented_stop_commands
    session = ServerSession.new

    stdout, stderr, status = session.health_command
    assert status.success?, stderr
    assert_equal "Web UI ready\n", stdout
    assert_equal "", stderr
    assert_equal 0o600, File.stat(session.pid_file).mode & 0o777

    final = session.close
    session = nil
    assert final.fetch(:stop_status).success?, final.fetch(:stop_stderr)
    assert_match(/\ASent TERM to Web UI process \d+\n\z/, final.fetch(:stop_stdout))
    assert_equal "", final.fetch(:stop_stderr)
    assert final.fetch(:status).success?
    assert_includes final.fetch(:diagnostics), "text-stats web ready"
    assert_includes final.fetch(:diagnostics), "text-stats web stopped"
    assert_equal true, final.fetch(:pid_file_removed)
  ensure
    session&.close
  end

  def test_absent_readiness_and_stop_commands_fail_promptly
    listener = TCPServer.new("127.0.0.1", 0)
    port = listener.addr[1]
    listener.close
    listener = nil

    Dir.mktmpdir("text-stats-web-absent") do |directory|
      env = {
        "TEXT_STATS_WEB_BIND" => "127.0.0.1",
        "TEXT_STATS_WEB_PORT" => port.to_s,
        "TEXT_STATS_WEB_PID_FILE" => File.join(directory, "missing.pid"),
        "RUBYOPT" => nil
      }
      started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      health_stdout, health_stderr, health_status = Open3.capture3(
        env, *COMMAND, "--health", chdir: ROOT
      )
      elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - started

      refute health_status.success?
      assert_equal "", health_stdout
      assert_includes health_stderr, "Web UI readiness check failed"
      assert_operator elapsed, :<, 3.0

      stop_stdout, stop_stderr, stop_status = Open3.capture3(
        env, *COMMAND, "--stop", chdir: ROOT
      )
      refute stop_status.success?
      assert_equal "", stop_stdout
      assert_includes stop_stderr, "Web UI PID file not found"
    end
  ensure
    listener&.close
  end

  def test_pid_file_identity_and_symlink_safety
    Dir.mktmpdir("text-stats-web-pid-safety") do |directory|
      pid_file = File.join(directory, "server.pid")
      env = {
        "TEXT_STATS_WEB_ENABLED" => "1",
        "TEXT_STATS_WEB_BIND" => "127.0.0.1",
        "TEXT_STATS_WEB_PORT" => "0",
        "TEXT_STATS_WEB_PID_FILE" => pid_file,
        "RUBYOPT" => nil
      }

      stale_record = { "pid" => Process.pid, "startTicks" => "0" }
      File.write(pid_file, JSON.generate(stale_record) + "\n", mode: "w", perm: 0o600)

      stop_stdout, stop_stderr, stop_status = Open3.capture3(
        env, *COMMAND, "--stop", chdir: ROOT
      )
      refute stop_status.success?
      assert_equal "", stop_stdout
      assert_includes stop_stderr, "PID file is stale; refusing to signal process #{Process.pid}"

      start_stdout, start_stderr, start_status = Open3.capture3(
        env, *COMMAND, chdir: ROOT
      )
      assert_equal 78, start_status.exitstatus
      assert_equal "", start_stdout
      assert_includes start_stderr, "PID file already exists"
      assert_equal stale_record, JSON.parse(File.read(pid_file, encoding: "UTF-8"))

      File.delete(pid_file)
      target = File.join(directory, "target")
      File.write(target, "unchanged\n")
      File.symlink(target, pid_file)

      stop_stdout, stop_stderr, stop_status = Open3.capture3(
        env, *COMMAND, "--stop", chdir: ROOT
      )
      refute stop_status.success?
      assert_equal "", stop_stdout
      assert_includes stop_stderr, "regular non-symlink file"
      assert_equal "unchanged\n", File.read(target, encoding: "UTF-8")
    end
  end

  def test_fixed_port_collision_fails_promptly_without_hanging
    listener = TCPServer.new("127.0.0.1", 0)
    port = listener.addr[1]
    Dir.mktmpdir("text-stats-web-collision") do |directory|
      started = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      stdout, stderr, status = Open3.capture3(
        {
          "TEXT_STATS_WEB_ENABLED" => "1",
          "TEXT_STATS_WEB_BIND" => "127.0.0.1",
          "TEXT_STATS_WEB_PORT" => port.to_s,
          "TEXT_STATS_WEB_PID_FILE" => File.join(directory, "server.pid"),
          "RUBYOPT" => nil
        },
        *COMMAND,
        chdir: ROOT
      )
      elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - started

      refute status.success?
      assert_equal "", stdout
      assert_includes stderr, "unable to start Web UI"
      assert_operator elapsed, :<, 3.0
      refute File.exist?(File.join(directory, "server.pid"))
    end
  ensure
    listener&.close
  end
end
