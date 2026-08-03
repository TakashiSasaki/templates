# frozen_string_literal: true

require "json"
require "minitest/autorun"
require "open3"
require "rbconfig"
require "socket"
require "timeout"
require "tmpdir"
require_relative "../mcp/service_manager"

class TextStatsMcpManagedServiceTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  MANAGER = File.join(ROOT, "mcp/service_manager.rb")
  HTTP_SERVER = File.join(ROOT, "mcp/http_server.rb")
  TOKEN = "fixture-managed-token-0123456789abcdef"
  TEST_NONCE = "a" * 64

  def free_port
    socket = TCPServer.new("127.0.0.1", 0)
    socket.addr.fetch(1)
  ensure
    socket&.close
  end

  def runtime_environment(directory)
    token_file = File.join(directory, "token")
    File.write(token_file, "#{TOKEN}\n", mode: "wb")
    File.chmod(0o600, token_file)
    {
      "TEXT_STATS_MCP_HTTP_BIND" => "127.0.0.1",
      "TEXT_STATS_MCP_HTTP_PORT" => free_port.to_s,
      "TEXT_STATS_MCP_HTTP_TOKEN" => nil,
      "TEXT_STATS_MCP_HTTP_TOKEN_FILE" => token_file,
      "TEXT_STATS_MCP_HTTP_PID_FILE" => File.join(directory, "service.pid"),
      "TEXT_STATS_MCP_HTTP_LOG_FILE" => File.join(directory, "service.log")
    }
  end

  def record_for(pid, start_ticks: nil, nonce: TEST_NONCE)
    {
      "pid" => pid,
      "startTicks" => start_ticks || TextStatsMcp::ManagedService.proc_start_ticks(pid),
      "readinessNonce" => nonce
    }
  end

  def run_manager(action, environment, timeout: 20)
    Timeout.timeout(timeout) do
      Open3.capture3(
        environment,
        RbConfig.ruby,
        MANAGER,
        action,
        chdir: ROOT
      )
    end
  end

  def http_json(port, path = "/readyz")
    socket = TCPSocket.new("127.0.0.1", port)
    socket.write(
      "GET #{path} HTTP/1.1\r\n" \
      "Host: 127.0.0.1:#{port}\r\n" \
      "Accept: application/json\r\n" \
      "Connection: close\r\n\r\n"
    )
    raw = socket.read
    _header, body = raw.split("\r\n\r\n", 2)
    JSON.parse(body)
  ensure
    socket&.close
  end

  def wait_for_http(port, expected: { "status" => "ready" })
    Timeout.timeout(8) do
      loop do
        begin
          return if http_json(port) == expected
        rescue SystemCallError, JSON::ParserError
          nil
        end
        sleep 0.05
      end
    end
  end

  def terminate_group(pid)
    return unless pid

    begin
      Process.kill("TERM", -pid)
    rescue Errno::ESRCH
      nil
    end
    begin
      Timeout.timeout(2) { Process.wait(pid) }
    rescue Timeout::Error
      begin
        Process.kill("KILL", -pid)
      rescue Errno::ESRCH
        nil
      end
      begin
        Process.wait(pid)
      rescue Errno::ECHILD
        nil
      end
    rescue Errno::ECHILD
      nil
    end
  end

  def test_managed_start_readiness_liveness_restart_and_stop
    Dir.mktmpdir("mcp-managed-service") do |directory|
      environment = runtime_environment(directory)
      begin
        stdout, stderr, status = run_manager("start", environment)
        assert status.success?, "stdout=#{stdout.inspect} stderr=#{stderr.inspect}"
        record = JSON.parse(File.read(environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")))
        first_pid = record.fetch("pid")
        assert_operator first_pid, :>, 0
        assert_match(/\A[0-9a-f]{64}\z/, record.fetch("readinessNonce"))

        stdout, stderr, status = run_manager("ready", environment)
        assert status.success?, "stdout=#{stdout.inspect} stderr=#{stderr.inspect}"
        assert_includes stdout, "ready"

        stdout, stderr, status = run_manager("live", environment)
        assert status.success?, "stdout=#{stdout.inspect} stderr=#{stderr.inspect}"
        assert_includes stdout, "live"

        stdout, stderr, status = run_manager("restart", environment)
        assert status.success?, "stdout=#{stdout.inspect} stderr=#{stderr.inspect}"
        replacement = JSON.parse(File.read(environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")))
        refute_equal first_pid, replacement.fetch("pid")
        refute_equal record.fetch("readinessNonce"), replacement.fetch("readinessNonce")

        _stdout, stderr, status = run_manager("stop", environment)
        assert status.success?, stderr
        refute_path_exists environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")

        _stdout, stderr, status = run_manager("live", environment)
        refute status.success?
        assert_includes stderr, "not running"
      ensure
        run_manager("stop", environment) if File.exist?(environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE"))
      end

      log = File.read(environment.fetch("TEXT_STATS_MCP_HTTP_LOG_FILE"))
      refute_includes log, TOKEN
    end
  end

  def test_manual_listener_cannot_satisfy_managed_readiness
    Dir.mktmpdir("mcp-managed-port-conflict") do |directory|
      environment = runtime_environment(directory)
      port = Integer(environment.fetch("TEXT_STATS_MCP_HTTP_PORT"), 10)
      manual_log = File.open(File.join(directory, "manual.log"), "wb")
      manual_pid = Process.spawn(
        {
          "TEXT_STATS_MCP_HTTP_BIND" => "127.0.0.1",
          "TEXT_STATS_MCP_HTTP_PORT" => port.to_s,
          "TEXT_STATS_MCP_HTTP_TOKEN" => TOKEN,
          "TEXT_STATS_MCP_HTTP_TOKEN_FILE" => nil,
          "TEXT_STATS_MCP_MANAGED_INSTANCE_NONCE" => nil
        },
        RbConfig.ruby,
        HTTP_SERVER,
        chdir: ROOT,
        in: File::NULL,
        out: manual_log,
        err: manual_log,
        pgroup: true,
        close_others: true
      )
      wait_for_http(port)
      environment["TEXT_STATS_MCP_TEST_MODE"] = "1"
      environment["TEXT_STATS_MCP_TEST_STARTUP_DELAY"] = "0.5"

      _stdout, stderr, status = run_manager("start", environment)

      refute status.success?
      assert_match(/exited before readiness|readiness deadline exceeded/, stderr)
      refute_path_exists environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")
      assert_equal({ "status" => "ready" }, http_json(port))
    ensure
      manual_log&.close
      terminate_group(manual_pid)
    end
  end

  def test_lifecycle_lock_serializes_commands
    Dir.mktmpdir("mcp-managed-lock") do |directory|
      environment = runtime_environment(directory)
      configuration = TextStatsMcp::ManagedService.configuration_from(environment)
      reader, writer = IO.pipe
      pid = fork do
        reader.close
        TextStatsMcp::ManagedService.with_lifecycle_lock(configuration) do
          writer.write("1")
          writer.flush
          sleep 0.5
        end
        writer.close
        exit! 0
      end
      writer.close
      assert_equal "1", Timeout.timeout(2) { reader.read(1) }
      started = Process.clock_gettime(Process::CLOCK_MONOTONIC)

      TextStatsMcp::ManagedService.with_lifecycle_lock(configuration) { nil }

      elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - started
      assert_operator elapsed, :>=, 0.35
      Process.wait(pid)
    ensure
      reader&.close
      writer&.close unless writer&.closed?
      begin
        Process.kill("KILL", pid) if pid
      rescue Errno::ESRCH
        nil
      end
      begin
        Process.wait(pid) if pid
      rescue Errno::ECHILD
        nil
      end
    end
  end

  def test_insecure_token_is_rejected_before_process_or_pid_creation
    Dir.mktmpdir("mcp-managed-token") do |directory|
      environment = runtime_environment(directory)
      File.chmod(0o644, environment.fetch("TEXT_STATS_MCP_HTTP_TOKEN_FILE"))

      _stdout, stderr, status = run_manager("start", environment)

      assert_equal TextStatsMcp::ManagedService::CONFIGURATION_EXIT, status.exitstatus
      assert_includes stderr, "must not be accessible by group or other users"
      refute_path_exists environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")
      refute_path_exists environment.fetch("TEXT_STATS_MCP_HTTP_LOG_FILE")
    end
  end

  def test_missing_token_is_a_configuration_failure
    Dir.mktmpdir("mcp-managed-token-missing") do |directory|
      environment = runtime_environment(directory)
      token_file = environment.fetch("TEXT_STATS_MCP_HTTP_TOKEN_FILE")
      File.unlink(token_file)

      _stdout, stderr, status = run_manager("start", environment)

      assert_equal TextStatsMcp::ManagedService::CONFIGURATION_EXIT, status.exitstatus
      assert_includes stderr, "MCP HTTP token file does not exist"
      assert_includes stderr, token_file
      refute_path_exists environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")
      refute_path_exists environment.fetch("TEXT_STATS_MCP_HTTP_LOG_FILE")
    end
  end

  def test_symlink_token_is_rejected_before_process_creation
    Dir.mktmpdir("mcp-managed-token-link") do |directory|
      environment = runtime_environment(directory)
      real_token = environment.fetch("TEXT_STATS_MCP_HTTP_TOKEN_FILE")
      linked_token = File.join(directory, "linked-token")
      File.symlink(real_token, linked_token)
      environment["TEXT_STATS_MCP_HTTP_TOKEN_FILE"] = linked_token

      _stdout, stderr, status = run_manager("start", environment)

      assert_equal TextStatsMcp::ManagedService::CONFIGURATION_EXIT, status.exitstatus
      assert_includes stderr, "must not be a symbolic link"
      refute_path_exists environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")
    end
  end

  def test_log_hardlink_to_token_is_rejected_without_modifying_secret
    Dir.mktmpdir("mcp-managed-token-log-alias") do |directory|
      environment = runtime_environment(directory)
      token_file = environment.fetch("TEXT_STATS_MCP_HTTP_TOKEN_FILE")
      log_file = environment.fetch("TEXT_STATS_MCP_HTTP_LOG_FILE")
      original = File.binread(token_file)
      File.link(token_file, log_file)

      _stdout, stderr, status = run_manager("start", environment)

      assert_equal TextStatsMcp::ManagedService::CONFIGURATION_EXIT, status.exitstatus
      assert_includes stderr, "must not reference the same file"
      assert_equal original, File.binread(token_file)
      refute_path_exists environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")
    end
  end

  def test_stale_pid_record_is_replaced_on_start
    Dir.mktmpdir("mcp-managed-stale") do |directory|
      environment = runtime_environment(directory)
      pid_file = environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")
      stale = record_for(999_999_999, start_ticks: "1")
      File.write(pid_file, JSON.generate(stale) + "\n")
      File.chmod(0o600, pid_file)

      begin
        stdout, stderr, status = run_manager("start", environment)
        assert status.success?, "stdout=#{stdout.inspect} stderr=#{stderr.inspect}"
        assert_includes stdout, "Removed stale"
        current = JSON.parse(File.read(pid_file))
        refute_equal 999_999_999, current.fetch("pid")
      ensure
        run_manager("stop", environment) if File.exist?(pid_file)
      end
    end
  end

  def test_symlink_pid_record_is_refused_without_touching_target
    Dir.mktmpdir("mcp-managed-pid-link") do |directory|
      environment = runtime_environment(directory)
      target = File.join(directory, "target.json")
      original = JSON.generate(record_for(999_999_999, start_ticks: "1")) + "\n"
      File.write(target, original)
      File.chmod(0o600, target)
      File.symlink(target, environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE"))

      _stdout, stderr, status = run_manager("start", environment)

      assert_equal TextStatsMcp::ManagedService::CONFIGURATION_EXIT, status.exitstatus
      assert_includes stderr, "must not be a symbolic link"
      assert_equal original, File.read(target)
    end
  end

  def test_existing_world_writable_runtime_directory_is_rejected
    Dir.mktmpdir("mcp-managed-runtime-mode") do |directory|
      environment = runtime_environment(directory)
      runtime = File.join(directory, "runtime")
      Dir.mkdir(runtime)
      File.chmod(0o777, runtime)
      environment["TEXT_STATS_MCP_HTTP_PID_FILE"] = File.join(runtime, "service.pid")
      environment["TEXT_STATS_MCP_HTTP_LOG_FILE"] = File.join(runtime, "service.log")

      _stdout, stderr, status = run_manager("start", environment)

      assert_equal TextStatsMcp::ManagedService::CONFIGURATION_EXIT, status.exitstatus
      assert_includes stderr, "must not be writable by group or other users"
      refute_path_exists environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")
      refute_path_exists environment.fetch("TEXT_STATS_MCP_HTTP_LOG_FILE")
    end
  end

  def test_symlinked_runtime_directory_is_rejected
    Dir.mktmpdir("mcp-managed-runtime-link") do |directory|
      environment = runtime_environment(directory)
      target = File.join(directory, "runtime-target")
      link = File.join(directory, "runtime-link")
      Dir.mkdir(target, 0o700)
      File.symlink(target, link)
      environment["TEXT_STATS_MCP_HTTP_PID_FILE"] = File.join(link, "service.pid")
      environment["TEXT_STATS_MCP_HTTP_LOG_FILE"] = File.join(link, "service.log")

      _stdout, stderr, status = run_manager("start", environment)

      assert_equal TextStatsMcp::ManagedService::CONFIGURATION_EXIT, status.exitstatus
      assert_includes stderr, "non-symlink directory"
      refute_path_exists File.join(target, "service.pid")
      refute_path_exists File.join(target, "service.log")
    end
  end

  def test_failed_start_cleanup_retains_record_when_process_survives
    Dir.mktmpdir("mcp-managed-cleanup") do |directory|
      environment = runtime_environment(directory)
      pid_file = environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")
      record = record_for(999_999_999, start_ticks: "1")
      TextStatsMcp::ManagedService.write_pid_record(pid_file, record)

      result = TextStatsMcp::ManagedService.stub(:terminate_recorded_process, false) do
        TextStatsMcp::ManagedService.cleanup_recorded_start_failure(pid_file, record)
      end

      refute result
      assert_equal record, JSON.parse(File.read(pid_file))
    end
  end

  def test_stop_escalates_and_removes_record_for_term_ignoring_process
    Dir.mktmpdir("mcp-managed-escalation") do |directory|
      environment = runtime_environment(directory)
      reader, writer = IO.pipe
      pid = Process.spawn(
        RbConfig.ruby,
        "-e",
        'ready = IO.new(3); Signal.trap("TERM") {}; ready.write("1"); ready.close; loop { sleep 1 }',
        3 => writer,
        pgroup: true,
        out: File::NULL,
        err: File::NULL,
        close_others: true
      )
      writer.close
      assert_equal "1", Timeout.timeout(2) { reader.read(1) }
      record = record_for(pid)
      TextStatsMcp::ManagedService.write_pid_record(
        environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE"),
        record
      )

      stdout, stderr, status = run_manager("stop", environment, timeout: 10)

      assert status.success?, "stdout=#{stdout.inspect} stderr=#{stderr.inspect}"
      assert_includes stdout, "stopped"
      refute_path_exists environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")
      _waited_pid, waited_status = Process.wait2(pid)
      assert waited_status.signaled?
      assert_equal Signal.list.fetch("KILL"), waited_status.termsig
    ensure
      reader&.close
      writer&.close unless writer&.closed?
      begin
        Process.kill("KILL", -pid) if pid
      rescue Errno::ESRCH
        nil
      end
      begin
        Process.wait(pid) if pid
      rescue Errno::ECHILD
        nil
      end
    end
  end
end
