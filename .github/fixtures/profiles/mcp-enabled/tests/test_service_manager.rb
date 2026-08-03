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
  TOKEN = "fixture-managed-token-0123456789abcdef"

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

  def test_managed_start_readiness_liveness_restart_and_stop
    Dir.mktmpdir("mcp-managed-service") do |directory|
      environment = runtime_environment(directory)
      begin
        stdout, stderr, status = run_manager("start", environment)
        assert status.success?, "stdout=#{stdout.inspect} stderr=#{stderr.inspect}"
        record = JSON.parse(File.read(environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")))
        first_pid = record.fetch("pid")
        assert_operator first_pid, :>, 0

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

  def test_stale_pid_record_is_replaced_on_start
    Dir.mktmpdir("mcp-managed-stale") do |directory|
      environment = runtime_environment(directory)
      pid_file = environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE")
      File.write(pid_file, JSON.generate("pid" => 999_999_999, "startTicks" => "1") + "\n")
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
      original = JSON.generate("pid" => 999_999_999, "startTicks" => "1") + "\n"
      File.write(target, original)
      File.chmod(0o600, target)
      File.symlink(target, environment.fetch("TEXT_STATS_MCP_HTTP_PID_FILE"))

      _stdout, stderr, status = run_manager("start", environment)

      assert_equal TextStatsMcp::ManagedService::CONFIGURATION_EXIT, status.exitstatus
      assert_includes stderr, "must not be a symbolic link"
      assert_equal original, File.read(target)
    end
  end

  def test_stop_escalates_and_removes_record_for_term_ignoring_process
    Dir.mktmpdir("mcp-managed-escalation") do |directory|
      environment = runtime_environment(directory)
      pid = Process.spawn(
        RbConfig.ruby,
        "-e",
        'Signal.trap("TERM") {}; loop { sleep 1 }',
        pgroup: true,
        out: File::NULL,
        err: File::NULL
      )
      record = {
        "pid" => pid,
        "startTicks" => TextStatsMcp::ManagedService.proc_start_ticks(pid)
      }
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
