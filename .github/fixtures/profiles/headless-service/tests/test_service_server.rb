# frozen_string_literal: true

require "fileutils"
require "json"
require "minitest/autorun"
require "net/http"
require "open3"
require "rbconfig"
require "socket"
require "stringio"
require "tempfile"
require "timeout"
require "tmpdir"
require "uri"
require_relative "../service/server"

class TextStatsServiceTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  TOKEN = "test-token-0123456789-abcdefghijklmnopqrstuvwxyz"

  FakeRequest = Struct.new(:request_method, :path, :headers, :body_proc) do
    def [](name)
      headers[name.downcase]
    end

    def body(&block)
      body_proc.call(block)
    end
  end

  class FakeResponse
    attr_accessor :status, :body

    def initialize
      @headers = {}
    end

    def []=(name, value)
      @headers[name.downcase] = value
    end

    def [](name)
      @headers[name.downcase]
    end
  end

  def setup
    @temporary_directory = Dir.mktmpdir("text-stats-service-test")
    @token_file = File.join(@temporary_directory, "token")
    File.write(@token_file, "#{TOKEN}\n", mode: "w", perm: 0o600)
    File.chmod(0o600, @token_file)
    @pid_file = File.join(@temporary_directory, "service.pid")
    @process = nil
    @stdout_file = nil
    @stderr_file = nil
  end

  def teardown
    stop_spawned_service
    FileUtils.remove_entry(@temporary_directory) if File.directory?(@temporary_directory)
  end

  def base_env(port: "0", pid_file: @pid_file, token_file: @token_file)
    env = {
      "TEXT_STATS_SERVICE_PORT" => port,
      "TEXT_STATS_SERVICE_PID_FILE" => pid_file
    }
    env["TEXT_STATS_SERVICE_TOKEN_FILE"] = token_file if token_file
    env
  end

  def run_command(*command, env: {}, timeout: 10)
    stdout = ""
    stderr = ""
    status = nil
    Timeout.timeout(timeout) do
      stdout, stderr, status = Open3.capture3(env, *command, chdir: ROOT)
    end
    [stdout, stderr, status]
  rescue Timeout::Error
    flunk("command timed out: #{command.inspect}")
  end

  def start_service(env: {})
    @stdout_file = Tempfile.new("service-stdout")
    @stderr_file = Tempfile.new("service-stderr")
    @process = Process.spawn(
      base_env.merge(env),
      RbConfig.ruby,
      "service/server.rb",
      chdir: ROOT,
      in: File::NULL,
      out: @stdout_file.path,
      err: @stderr_file.path
    )

    deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + 8
    loop do
      diagnostics = File.binread(@stderr_file.path)
      if (match = diagnostics.match(/text-stats service ready http:\/\/127\.0\.0\.1:(\d+)\//))
        @port = Integer(match[1], 10)
        break
      end
      unless process_alive?(@process)
        _pid, status = Process.wait2(@process)
        @process = nil
        flunk("service exited before readiness: status=#{status.exitstatus}, diagnostics=#{diagnostics.inspect}")
      end
      flunk("service did not become ready: #{diagnostics.inspect}") if Process.clock_gettime(Process::CLOCK_MONOTONIC) >= deadline
      sleep 0.05
    end
  end

  def stop_spawned_service
    return unless @process

    begin
      Process.kill("TERM", @process)
    rescue Errno::ESRCH
      nil
    end
    begin
      Timeout.timeout(3) { Process.wait(@process) }
    rescue Timeout::Error
      begin
        Process.kill("KILL", @process)
      rescue Errno::ESRCH
        nil
      end
      Process.wait(@process)
    rescue Errno::ECHLD
      nil
    end
    @process = nil
    @stdout_file&.close!
    @stderr_file&.close!
  end

  def process_alive?(pid)
    Process.kill(0, pid)
    true
  rescue Errno::ESRCH
    false
  end

  def request(method, path, body: nil, token: TOKEN, host: nil, origin: nil, content_type: "application/json")
    uri = URI("http://127.0.0.1:#{@port}#{path}")
    klass = Net::HTTP.const_get(method.capitalize)
    message = klass.new(uri)
    message["Host"] = host if host
    message["Origin"] = origin if origin
    message["Authorization"] = "Bearer #{token}" if token
    message["Content-Type"] = content_type if content_type
    message.body = body if body
    http = Net::HTTP.new(uri.host, uri.port, nil, nil, nil, nil)
    http.open_timeout = 2
    http.read_timeout = 4
    http.start { |client| client.request(message) }
  end

  def json(response)
    JSON.parse(response.body)
  end

  def test_configuration_and_token_file_guards
    stdout, stderr, status = run_command(RbConfig.ruby, "service/server.rb", env: base_env(token_file: nil))
    assert_equal 78, status.exitstatus
    assert_empty stdout
    assert_includes stderr, "TEXT_STATS_SERVICE_TOKEN_FILE is required"

    stdout, stderr, status = run_command(
      RbConfig.ruby,
      "service/server.rb",
      env: base_env.merge("TEXT_STATS_SERVICE_BIND" => "0.0.0.0")
    )
    assert_equal 78, status.exitstatus
    assert_empty stdout
    assert_includes stderr, "must be 127.0.0.1"

    File.chmod(0o644, @token_file)
    _stdout, stderr, status = run_command(RbConfig.ruby, "service/server.rb", env: base_env)
    assert_equal 78, status.exitstatus
    assert_includes stderr, "must not be accessible by group or other users"
    File.chmod(0o600, @token_file)

    target = File.join(@temporary_directory, "token-target")
    File.write(target, TOKEN, mode: "w", perm: 0o600)
    symlink = File.join(@temporary_directory, "token-link")
    File.symlink(target, symlink)
    _stdout, stderr, status = run_command(
      RbConfig.ruby,
      "service/server.rb",
      env: base_env(token_file: symlink)
    )
    assert_equal 78, status.exitstatus
    assert_includes stderr, "regular non-symlink"
  end

  def test_http_contract_authentication_and_non_browser_boundary
    start_service

    live = request("get", "/livez", token: nil, content_type: nil)
    assert_equal "200", live.code
    assert_equal({ "ok" => true, "status" => "live" }, json(live))

    ready = request("get", "/readyz", token: nil, content_type: nil)
    assert_equal "200", ready.code
    assert_equal({ "ok" => true, "status" => "ready" }, json(ready))

    body = JSON.generate("text" => "alpha beta\n")
    success = request("post", "/v1/text-stats", body: body)
    assert_equal "200", success.code
    assert_equal(
      {
        "contractVersion" => 1,
        "ok" => true,
        "result" => { "bytes" => 11, "lines" => 1, "words" => 2 }
      },
      json(success)
    )
    refute_includes success.body, "alpha"
    assert_equal "no-store", success["cache-control"]
    assert_equal "nosniff", success["x-content-type-options"]
    assert_equal "DENY", success["x-frame-options"]
    assert_nil success["access-control-allow-origin"]

    missing = request("post", "/v1/text-stats", body: body, token: nil)
    assert_equal "401", missing.code
    assert_equal 'Bearer realm="text-stats-service"', missing["www-authenticate"]

    wrong = request("post", "/v1/text-stats", body: body, token: "x" * 40)
    assert_equal "401", wrong.code

    browser = request(
      "post",
      "/v1/text-stats",
      body: body,
      origin: "http://127.0.0.1:#{@port}"
    )
    assert_equal "403", browser.code
    assert_equal "browser-origin requests are not supported", json(browser).fetch("error")

    invalid_host = request("get", "/livez", token: nil, content_type: nil, host: "example.test")
    assert_equal "403", invalid_host.code

    method_failure = request("get", "/v1/text-stats", token: nil, content_type: nil)
    assert_equal "405", method_failure.code
    assert_equal "POST", method_failure["allow"]

    missing_route = request("get", "/missing", token: nil, content_type: nil)
    assert_equal "404", missing_route.code

    diagnostics = File.binread(@stderr_file.path)
    refute_includes diagnostics, TOKEN
    refute_includes diagnostics, "alpha beta"
  end

  def test_validation_size_limits_and_health_isolation
    start_service

    wrong_type = request("post", "/v1/text-stats", body: "{}", content_type: "text/plain")
    assert_equal "415", wrong_type.code

    invalid_utf8 = request("post", "/v1/text-stats", body: [0xFF].pack("C"))
    assert_equal "400", invalid_utf8.code
    assert_equal "request body is not valid UTF-8", json(invalid_utf8).fetch("error")

    invalid_json = request("post", "/v1/text-stats", body: "{")
    assert_equal "400", invalid_json.code

    invalid_schema = request("post", "/v1/text-stats", body: JSON.generate("text" => "x", "extra" => true))
    assert_equal "422", invalid_schema.code

    oversized = request("post", "/v1/text-stats", body: "x" * 65_537)
    assert_equal "413", oversized.code
    assert_equal "close", oversized["connection"].downcase

    raw = TCPSocket.new("127.0.0.1", @port)
    raw.write("POST /v1/text-stats HTTP/1.1\r\n")
    raw.write("Host: 127.0.0.1:#{@port}\r\n")
    raw.write("Authorization: Bearer #{TOKEN}\r\n")
    raw.write("Content-Type: application/json\r\n")
    raw.write("Transfer-Encoding: chunked\r\n\r\n")
    raw.write("10000\r\n#{"x" * 65_536}\r\n")
    raw.write("1\r\nx\r\n0\r\n\r\n")
    response_text = Timeout.timeout(4) { raw.read }
    raw.close
    assert_match(/\AHTTP\/1\.1 413 /, response_text)
    assert_match(/Connection: close/i, response_text)

    assert_equal "200", request("get", "/readyz", token: nil, content_type: nil).code
    assert_equal "200", request("get", "/livez", token: nil, content_type: nil).code
  end

  def test_incomplete_request_times_out_and_releases_capacity
    start_service

    raw = TCPSocket.new("127.0.0.1", @port)
    raw.write("POST /v1/text-stats HTTP/1.1\r\n")
    raw.write("Host: 127.0.0.1:#{@port}\r\n")
    raw.write("Authorization: Bearer #{TOKEN}\r\n")
    raw.write("Content-Type: application/json\r\n")
    raw.write("Content-Length: 20\r\n\r\n{")
    response_text = Timeout.timeout(6) { raw.read }
    raw.close

    assert_match(/\AHTTP\/1\.1 408 /, response_text)
    assert_match(/Connection: close/i, response_text)
    assert_includes response_text, '"error":"request timed out"'

    success = request("post", "/v1/text-stats", body: JSON.generate("text" => "after timeout"))
    assert_equal "200", success.code
    assert_equal "200", request("get", "/readyz", token: nil, content_type: nil).code
  end

  def test_concurrency_gate_is_bounded_and_health_remains_available
    diagnostic = StringIO.new
    application = TextStatsService::Application.new(port: 4568, token: TOKEN, diagnostic: diagnostic)
    entered = Queue.new
    release = Queue.new
    first_request = fake_post do |block|
      entered << true
      release.pop
      block.call(JSON.generate("text" => "first"))
    end
    first_response = FakeResponse.new

    worker = Thread.new { application.service(first_request, first_response) }
    entered.pop

    second_response = FakeResponse.new
    application.service(fake_post { |block| block.call(JSON.generate("text" => "second")) }, second_response)
    assert_equal 503, second_response.status
    assert_equal "service is busy or draining", JSON.parse(second_response.body).fetch("error")

    ready_response = FakeResponse.new
    ready_request = FakeRequest.new("GET", "/readyz", { "host" => "127.0.0.1:4568" }, proc { |_block| })
    application.service(ready_request, ready_response)
    assert_equal 200, ready_response.status

    release << true
    worker.join(2)
    refute worker.alive?
    assert_equal 200, first_response.status
  ensure
    release << true if worker&.alive?
    worker&.join(1)
  end

  def test_health_commands_and_identity_verified_shutdown
    start_service
    env = base_env(port: @port.to_s)

    stdout, stderr, status = run_command(RbConfig.ruby, "service/server.rb", "--health", env: env)
    assert status.success?, stderr
    assert_equal "Headless service ready\n", stdout

    stdout, stderr, status = run_command(RbConfig.ruby, "service/server.rb", "--live", env: env)
    assert status.success?, stderr
    assert_equal "Headless service live\n", stdout

    record = JSON.parse(File.read(@pid_file, encoding: "UTF-8"))
    assert_equal @process, record.fetch("pid")
    assert_match(/\A\d+\z/, record.fetch("startTicks"))
    assert_equal 0, File.stat(@pid_file).mode & 0o077

    stdout, stderr, status = run_command(RbConfig.ruby, "service/server.rb", "--stop", env: env)
    assert status.success?, stderr
    assert_includes stdout, "Sent TERM"
    Timeout.timeout(4) { Process.wait(@process) }
    @process = nil
    refute File.exist?(@pid_file)
    assert_equal "", File.binread(@stdout_file.path)
    assert_includes File.binread(@stderr_file.path), "text-stats service stopped"
  end

  def test_stale_and_unsafe_pid_records_do_not_signal_unrelated_processes
    start_ticks = TextStatsService::ServerCommand.process_start_ticks(Process.pid)
    File.write(
      @pid_file,
      JSON.generate("pid" => Process.pid, "startTicks" => (Integer(start_ticks, 10) + 1).to_s),
      mode: "w",
      perm: 0o600
    )
    stdout, stderr, status = run_command(
      RbConfig.ruby,
      "service/server.rb",
      "--stop",
      env: base_env(port: "4568")
    )
    refute status.success?
    assert_empty stdout
    assert_includes stderr, "stale; refusing to signal"
    assert process_alive?(Process.pid)

    File.delete(@pid_file)
    File.write(@pid_file, "existing\n", mode: "w", perm: 0o600)
    stdout, stderr, status = run_command(RbConfig.ruby, "service/server.rb", env: base_env)
    refute status.success?
    assert_empty stdout
    assert_includes stderr, "PID file already exists"

    File.delete(@pid_file)
    target = File.join(@temporary_directory, "pid-target")
    File.write(target, "target\n")
    File.symlink(target, @pid_file)
    stdout, stderr, status = run_command(RbConfig.ruby, "service/server.rb", env: base_env)
    refute status.success?
    assert_empty stdout
    assert_includes stderr, "PID file already exists"
    assert_equal "target\n", File.read(target)
  end

  def test_fixed_port_collision_fails_promptly
    blocker = TCPServer.new("127.0.0.1", 0)
    port = blocker.addr[1]
    stdout, stderr, status = run_command(
      RbConfig.ruby,
      "service/server.rb",
      env: base_env(port: port.to_s),
      timeout: 5
    )
    refute status.success?
    assert_empty stdout
    assert_includes stderr, "unable to start headless service"
  ensure
    blocker&.close
  end

  private

  def fake_post(&body_proc)
    FakeRequest.new(
      "POST",
      "/v1/text-stats",
      {
        "host" => "127.0.0.1:4568",
        "authorization" => "Bearer #{TOKEN}",
        "content-type" => "application/json"
      },
      body_proc
    )
  end
end
