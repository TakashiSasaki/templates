#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "open3"
require "rbconfig"
require "tempfile"
require "timeout"
require "tmpdir"

fixture_root = File.expand_path("../fixtures/profiles/headless-service", __dir__)
service_entry = File.join(fixture_root, "service/server.rb")
token = "restrictive-umask-test-token-0123456789-abcdef"
service_pid = nil
stdout_file = nil
stderr_file = nil

process_alive = lambda do |pid|
  Process.kill(0, pid)
  true
rescue Errno::ESRCH
  false
end

begin
  Dir.mktmpdir("headless-service-restrictive-umask") do |directory|
    runtime_directory = File.join(directory, "fresh-runtime")
    Dir.mkdir(runtime_directory, 0o700)
    token_file = File.join(directory, "token")
    pid_directory = File.join(runtime_directory, "tmp")
    pid_file = File.join(pid_directory, "text-stats-service.pid")
    File.write(token_file, "#{token}\n", mode: "w", perm: 0o600)
    File.chmod(0o600, token_file)

    stdout_file = Tempfile.new("headless-umask-stdout")
    stderr_file = Tempfile.new("headless-umask-stderr")
    environment = {
      "TEXT_STATS_SERVICE_TOKEN_FILE" => token_file,
      "TEXT_STATS_SERVICE_PORT" => "0"
    }

    service_pid = Process.spawn(
      environment,
      RbConfig.ruby,
      service_entry,
      chdir: runtime_directory,
      umask: 0o777,
      in: File::NULL,
      out: stdout_file.path,
      err: stderr_file.path
    )

    deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + 8
    loop do
      diagnostics = File.binread(stderr_file.path)
      break if File.file?(pid_file) && diagnostics.include?("text-stats service ready")

      unless process_alive.call(service_pid)
        _pid, status = Process.wait2(service_pid)
        service_pid = nil
        raise "service exited before readiness: status=#{status.exitstatus}, diagnostics=#{diagnostics.inspect}"
      end
      if Process.clock_gettime(Process::CLOCK_MONOTONIC) >= deadline
        raise "service did not become ready under restrictive umask: #{diagnostics.inspect}"
      end
      sleep 0.05
    end

    directory_mode = File.stat(pid_directory).mode & 0o777
    unless directory_mode == 0o700
      raise format("expected default PID directory mode 0700, got %04o", directory_mode)
    end

    mode = File.stat(pid_file).mode & 0o777
    raise format("expected PID record mode 0600, got %04o", mode) unless mode == 0o600

    record = JSON.parse(File.read(pid_file, encoding: "UTF-8"))
    raise "PID record does not identify the service process" unless record.fetch("pid") == service_pid

    stop_stdout, stop_stderr, stop_status = Open3.capture3(
      environment,
      RbConfig.ruby,
      service_entry,
      "--stop",
      chdir: runtime_directory
    )
    unless stop_status.success?
      raise "--stop failed under restrictive umask: stdout=#{stop_stdout.inspect}, stderr=#{stop_stderr.inspect}"
    end
    raise "--stop did not report TERM delivery" unless stop_stdout.include?("Sent TERM")

    Timeout.timeout(5) { Process.wait(service_pid) }
    service_pid = nil
    raise "PID record remained after graceful shutdown" if File.exist?(pid_file) || File.symlink?(pid_file)
    raise "service wrote unexpected stdout" unless File.binread(stdout_file.path).empty?
    unless File.binread(stderr_file.path).include?("text-stats service stopped")
      raise "service did not report graceful shutdown"
    end
  end

  puts "Restrictive-umask default-path lifecycle test passed."
rescue StandardError => error
  warn error.message
  exit 1
ensure
  if service_pid
    begin
      Process.kill("KILL", service_pid)
    rescue Errno::ESRCH
      nil
    end
    begin
      Process.wait(service_pid)
    rescue Errno::ECHILD
      nil
    end
  end
  stdout_file&.close!
  stderr_file&.close!
end
