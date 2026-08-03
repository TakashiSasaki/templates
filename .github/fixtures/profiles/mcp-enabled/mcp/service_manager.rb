#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "optparse"
require "rbconfig"
require "securerandom"
require "socket"
require "timeout"

module TextStatsMcp
  module ManagedService
    ROOT = File.expand_path("..", __dir__)
    HTTP_SERVER = File.join(ROOT, "mcp/http_server.rb")
    DEFAULT_BIND = "127.0.0.1"
    DEFAULT_PORT = 4570
    DEFAULT_PID_FILE = "tmp/text-stats-mcp-http.pid"
    DEFAULT_LOG_FILE = "tmp/text-stats-mcp-http.log"
    CONFIGURATION_EXIT = 78
    PROBE_DEADLINE_SECONDS = 2
    START_DEADLINE_SECONDS = 8
    TERM_GRACE_SECONDS = 2
    KILL_GRACE_SECONDS = 1
    PID_RECORD_MAX_BYTES = 4096
    PID_RECORD_KEYS = %w[pid startTicks].freeze

    class ConfigurationError < StandardError; end
    class StateError < StandardError; end

    module_function

    def run(argv, env: ENV, stdout: $stdout, stderr: $stderr)
      parser = OptionParser.new do |options|
        options.banner = "Usage: ruby mcp/service_manager.rb <start|stop|restart|ready|live>"
        options.on("-h", "--help", "Show this help") do
          stdout.puts(options)
          return 0
        end
      end
      parser.parse!(argv)
      raise ConfigurationError, "exactly one lifecycle action is required" unless argv.length == 1

      action = argv.fetch(0)
      unless %w[start stop restart ready live].include?(action)
        raise ConfigurationError, "unsupported lifecycle action: #{action}"
      end

      configuration = configuration_from(env)
      case action
      when "start"
        start(configuration, env: env, stdout: stdout, stderr: stderr)
      when "stop"
        stop(configuration, stdout: stdout, stderr: stderr)
      when "restart"
        stop(configuration, stdout: stdout, stderr: stderr)
        start(configuration, env: env, stdout: stdout, stderr: stderr)
      when "ready"
        probe(configuration, "/readyz", "ready", stdout: stdout, stderr: stderr)
      when "live"
        probe(configuration, "/livez", "live", stdout: stdout, stderr: stderr)
      end
    rescue OptionParser::ParseError, ConfigurationError => error
      stderr.puts(error.message)
      CONFIGURATION_EXIT
    rescue StateError => error
      stderr.puts(error.message)
      1
    end

    def configuration_from(env)
      bind = env.fetch("TEXT_STATS_MCP_HTTP_BIND", DEFAULT_BIND)
      raise ConfigurationError, "TEXT_STATS_MCP_HTTP_BIND must be 127.0.0.1" unless bind == DEFAULT_BIND

      raw_port = env.fetch("TEXT_STATS_MCP_HTTP_PORT", DEFAULT_PORT.to_s)
      port = Integer(raw_port, 10)
      unless (1..65_535).cover?(port)
        raise ConfigurationError, "TEXT_STATS_MCP_HTTP_PORT must be between 1 and 65535"
      end

      pid_file = File.expand_path(env.fetch("TEXT_STATS_MCP_HTTP_PID_FILE", DEFAULT_PID_FILE), ROOT)
      log_file = File.expand_path(env.fetch("TEXT_STATS_MCP_HTTP_LOG_FILE", DEFAULT_LOG_FILE), ROOT)
      if pid_file == log_file
        raise ConfigurationError, "managed PID and log paths must be different"
      end

      token_file_value = env["TEXT_STATS_MCP_HTTP_TOKEN_FILE"]
      token_file = token_file_value && File.expand_path(token_file_value, ROOT)
      {
        bind: bind,
        port: port,
        pid_file: pid_file,
        log_file: log_file,
        token_file: token_file
      }
    rescue ArgumentError
      raise ConfigurationError, "TEXT_STATS_MCP_HTTP_PORT must be a base-10 integer between 1 and 65535"
    end

    def start(configuration, env:, stdout:, stderr:)
      validate_token_file(configuration.fetch(:token_file))
      clear_stale_record(configuration.fetch(:pid_file), stdout: stdout)
      log = open_private_log(configuration.fetch(:log_file))
      child_env = {
        "TEXT_STATS_MCP_HTTP_BIND" => configuration.fetch(:bind),
        "TEXT_STATS_MCP_HTTP_PORT" => configuration.fetch(:port).to_s,
        "TEXT_STATS_MCP_HTTP_TOKEN" => nil,
        "TEXT_STATS_MCP_HTTP_TOKEN_FILE" => configuration.fetch(:token_file),
        "TEXT_STATS_MCP_HTTP_PID_FILE" => nil,
        "TEXT_STATS_MCP_HTTP_LOG_FILE" => nil
      }
      pid = Process.spawn(
        child_env,
        RbConfig.ruby,
        HTTP_SERVER,
        chdir: ROOT,
        in: File::NULL,
        out: log,
        err: log,
        pgroup: true,
        close_others: true
      )
      record = { "pid" => pid, "startTicks" => wait_for_start_ticks(pid) }
      write_pid_record(configuration.fetch(:pid_file), record)
      Process.detach(pid)
      wait_until_ready(configuration, record)
      stdout.puts("Managed MCP HTTP service started with PID #{pid}")
      0
    rescue ConfigurationError, StateError, SystemCallError => error
      terminate_recorded_process(record || { "pid" => pid, "startTicks" => safe_start_ticks(pid) }) if pid
      remove_pid_record_if_same(configuration.fetch(:pid_file), record) if record
      stderr.puts("unable to start managed MCP HTTP service: #{error.message}")
      error.is_a?(ConfigurationError) ? CONFIGURATION_EXIT : 1
    ensure
      log&.close
    end

    def stop(configuration, stdout:, stderr:)
      path = configuration.fetch(:pid_file)
      record = read_pid_record(path, missing: :nil)
      unless record
        stdout.puts("Managed MCP HTTP service is not running")
        return 0
      end

      unless process_identity_matches?(record)
        remove_pid_record_if_same(path, record)
        stdout.puts("Removed stale managed MCP HTTP PID record")
        return 0
      end

      terminate_recorded_process(record)
      if process_identity_matches?(record)
        raise StateError, "managed MCP HTTP service did not stop after bounded escalation"
      end
      remove_pid_record_if_same(path, record)
      stdout.puts("Managed MCP HTTP service stopped")
      0
    rescue ConfigurationError, StateError, SystemCallError => error
      stderr.puts("unable to stop managed MCP HTTP service: #{error.message}")
      error.is_a?(ConfigurationError) ? CONFIGURATION_EXIT : 1
    end

    def probe(configuration, path, expected_status, stdout:, stderr:)
      record = read_pid_record(configuration.fetch(:pid_file), missing: :nil)
      raise StateError, "managed MCP HTTP service is not running" unless record
      unless process_identity_matches?(record)
        remove_pid_record_if_same(configuration.fetch(:pid_file), record)
        raise StateError, "managed MCP HTTP service PID record is stale"
      end

      status, payload = Timeout.timeout(PROBE_DEADLINE_SECONDS) do
        read_bounded_http_json(
          configuration.fetch(:bind),
          configuration.fetch(:port),
          path
        )
      end
      unless status == 200 && payload == { "status" => expected_status }
        raise StateError, "managed MCP HTTP #{expected_status} probe failed with HTTP #{status}"
      end

      stdout.puts("Managed MCP HTTP service #{expected_status}")
      0
    rescue Timeout::Error
      stderr.puts("managed MCP HTTP #{expected_status} probe exceeded #{PROBE_DEADLINE_SECONDS} seconds")
      1
    rescue ConfigurationError, StateError, SystemCallError, JSON::ParserError => error
      stderr.puts(error.message)
      error.is_a?(ConfigurationError) ? CONFIGURATION_EXIT : 1
    end

    def wait_until_ready(configuration, record)
      deadline = monotonic_now + START_DEADLINE_SECONDS
      loop do
        raise StateError, "managed MCP HTTP service exited before readiness" unless process_identity_matches?(record)

        begin
          status, payload = Timeout.timeout(PROBE_DEADLINE_SECONDS) do
            read_bounded_http_json(
              configuration.fetch(:bind),
              configuration.fetch(:port),
              "/readyz"
            )
          end
          return if status == 200 && payload == { "status" => "ready" }
        rescue Timeout::Error, SystemCallError, JSON::ParserError, StateError
          nil
        end

        raise StateError, "managed MCP HTTP readiness deadline exceeded" if monotonic_now >= deadline

        sleep 0.05
      end
    end

    def validate_token_file(path)
      raise ConfigurationError, "TEXT_STATS_MCP_HTTP_TOKEN_FILE is required for managed startup" unless path

      raw = open_private_file(path, "MCP HTTP token file") do |file|
        content = file.read(4097).to_s
        if content.bytesize > 4096
          raise ConfigurationError, "MCP HTTP token file exceeds 4096 bytes: #{path}"
        end
        content
      end
      token = raw.sub(/\r?\n\z/, "")
      unless /\A[!-~]{32,128}\z/.match?(token)
        raise ConfigurationError, "MCP HTTP token must contain 32 to 128 visible ASCII characters"
      end
      true
    end

    def open_private_log(path)
      directory = ensure_private_directory(File.dirname(path))
      path = File.join(directory, File.basename(path))
      flags = File::WRONLY | File::CREAT | File::APPEND | File::NOFOLLOW
      file = File.open(path, flags, 0o600)
      file.chmod(0o600)
      validate_private_stat(file.stat, path, "managed MCP HTTP log")
      file.sync = true
      file
    rescue Errno::ELOOP
      raise ConfigurationError, "managed MCP HTTP log must not be a symbolic link: #{path}"
    rescue ConfigurationError
      raise
    rescue SystemCallError => error
      raise ConfigurationError, "unable to open managed MCP HTTP log #{path}: #{error.message}"
    end

    def open_private_file(path, description)
      flags = File::RDONLY | File::NOFOLLOW | File::NONBLOCK
      File.open(path, flags) do |file|
        validate_private_stat(file.stat, path, description)
        return yield(file)
      end
    rescue Errno::ELOOP
      raise ConfigurationError, "#{description} must not be a symbolic link: #{path}"
    rescue Errno::ENOENT
      raise
    rescue ConfigurationError
      raise
    rescue SystemCallError => error
      raise ConfigurationError, "unable to read #{description.downcase} #{path}: #{error.message}"
    end

    def validate_private_stat(stat, path, description)
      raise ConfigurationError, "#{description} must be a regular file: #{path}" unless stat.file?
      raise ConfigurationError, "#{description} must be owned by the service user: #{path}" unless stat.uid == Process.euid
      unless (stat.mode & 0o077).zero?
        raise ConfigurationError, "#{description} must not be accessible by group or other users: #{path}"
      end
    end

    def clear_stale_record(path, stdout:)
      record = read_pid_record(path, missing: :nil)
      return unless record
      raise StateError, "managed MCP HTTP service is already running with PID #{record.fetch("pid")}" if process_identity_matches?(record)

      remove_pid_record_if_same(path, record)
      stdout.puts("Removed stale managed MCP HTTP PID record")
    end

    def read_pid_record(path, missing: :error)
      raw = open_private_file(path, "managed MCP HTTP PID record") do |file|
        content = file.read(PID_RECORD_MAX_BYTES + 1).to_s
        if content.bytesize > PID_RECORD_MAX_BYTES
          raise ConfigurationError, "managed MCP HTTP PID record exceeds #{PID_RECORD_MAX_BYTES} bytes: #{path}"
        end
        content
      end
      payload = JSON.parse(raw)
      unless payload.is_a?(Hash) && payload.keys.sort == PID_RECORD_KEYS.sort &&
             payload["pid"].is_a?(Integer) && payload["pid"].positive? &&
             payload["startTicks"].is_a?(String) && /\A\d+\z/.match?(payload["startTicks"])
        raise ConfigurationError, "managed MCP HTTP PID record has an invalid schema: #{path}"
      end
      payload
    rescue Errno::ENOENT
      return nil if missing == :nil
      raise ConfigurationError, "managed MCP HTTP PID record does not exist: #{path}"
    rescue JSON::ParserError
      raise ConfigurationError, "managed MCP HTTP PID record is not valid JSON: #{path}"
    end

    def write_pid_record(path, record)
      directory = ensure_private_directory(File.dirname(path))
      path = File.join(directory, File.basename(path))
      serialized = "#{JSON.generate(record)}\n"
      raise ConfigurationError, "managed MCP HTTP PID record is too large" if serialized.bytesize > PID_RECORD_MAX_BYTES

      temporary_path = nil
      file = nil
      linked = false
      identity = nil
      begin
        temporary_path, file = open_staging_file(directory, File.basename(path))
        file.chmod(0o600)
        validate_private_stat(file.stat, temporary_path, "managed MCP HTTP PID staging file")
        file.write(serialized)
        file.flush
        file.fsync
        file.rewind
        raise ConfigurationError, "unable to verify complete managed MCP HTTP PID record" unless file.read == serialized

        stat = file.stat
        identity = [stat.dev, stat.ino]
        File.link(temporary_path, path)
        linked = true
        published = File.lstat(path)
        unless published.file? && [published.dev, published.ino] == identity
          raise ConfigurationError, "unable to verify published managed MCP HTTP PID record: #{path}"
        end
      rescue Errno::EEXIST
        raise ConfigurationError, "managed MCP HTTP PID record already exists: #{path}"
      ensure
        failure = $!
        file&.close
        if failure && linked && identity
          begin
            current = File.lstat(path)
            File.unlink(path) if [current.dev, current.ino] == identity
          rescue SystemCallError
            nil
          end
        end
        begin
          File.unlink(temporary_path) if temporary_path
        rescue SystemCallError
          nil
        end
      end
    rescue ConfigurationError
      raise
    rescue SystemCallError => error
      raise ConfigurationError, "unable to write managed MCP HTTP PID record #{path}: #{error.message}"
    end

    def open_staging_file(directory, basename)
      16.times do
        path = File.join(directory, ".#{basename}.#{Process.pid}.#{SecureRandom.hex(12)}.tmp")
        begin
          return [
            path,
            File.open(path, File::RDWR | File::CREAT | File::EXCL | File::NOFOLLOW, 0o600)
          ]
        rescue Errno::EEXIST
          next
        end
      end
      raise ConfigurationError, "unable to allocate managed MCP HTTP PID staging file"
    end

    def ensure_private_directory(directory)
      expanded = File.expand_path(directory)
      current = File::SEPARATOR
      expanded.split(File::SEPARATOR).reject(&:empty?).each do |component|
        current = File.join(current, component)
        created = false
        begin
          stat = File.stat(current)
        rescue Errno::ENOENT
          begin
            Dir.mkdir(current, 0o700)
            created = true
          rescue Errno::EEXIST
            nil
          end
          File.chmod(0o700, current) if created
          stat = File.stat(current)
        end
        raise ConfigurationError, "managed runtime parent is not a directory: #{current}" unless stat.directory?
        next unless created
        unless stat.uid == Process.euid && (stat.mode & 0o777) == 0o700
          raise ConfigurationError, "managed runtime parent failed security validation: #{current}"
        end
      end
      expanded
    rescue ConfigurationError
      raise
    rescue SystemCallError => error
      raise ConfigurationError, "unable to prepare managed runtime directory #{directory}: #{error.message}"
    end

    def remove_pid_record_if_same(path, record)
      return unless record
      current = read_pid_record(path, missing: :nil)
      File.unlink(path) if current == record
    rescue Errno::ENOENT
      nil
    end

    def wait_for_start_ticks(pid)
      deadline = monotonic_now + 1
      loop do
        ticks = safe_start_ticks(pid)
        return ticks if ticks
        raise StateError, "managed child exited before identity capture" if monotonic_now >= deadline
        sleep 0.01
      end
    end

    def safe_start_ticks(pid)
      proc_start_ticks(pid)
    rescue SystemCallError, StateError
      nil
    end

    def proc_identity(pid)
      raw = File.binread("/proc/#{Integer(pid)}/stat", 4096)
      close_paren = raw.rindex(")")
      raise StateError, "unable to parse process identity for PID #{pid}" unless close_paren
      fields = raw.byteslice(close_paren + 2..).to_s.split
      state = fields[0]
      ticks = fields[19]
      unless state && ticks && /\A\d+\z/.match?(ticks)
        raise StateError, "unable to parse process start ticks for PID #{pid}"
      end
      [state, ticks]
    end

    def proc_start_ticks(pid)
      proc_identity(pid).fetch(1)
    end

    def process_identity_matches?(record)
      pid = record.fetch("pid")
      Process.kill(0, pid)
      state, ticks = proc_identity(pid)
      state != "Z" && ticks == record.fetch("startTicks")
    rescue Errno::ESRCH, Errno::ENOENT, StateError
      false
    rescue Errno::EPERM
      raise ConfigurationError, "unable to verify managed process identity for PID #{pid}"
    end

    def terminate_recorded_process(record)
      return unless record && record["startTicks"] && process_identity_matches?(record)
      pid = record.fetch("pid")
      signal_group("TERM", pid)
      return if wait_until_identity_gone(record, TERM_GRACE_SECONDS)

      signal_group("KILL", pid)
      wait_until_identity_gone(record, KILL_GRACE_SECONDS)
    end

    def signal_group(signal, pid)
      Process.kill(signal, -pid)
    rescue Errno::ESRCH
      Process.kill(signal, pid)
    end

    def wait_until_identity_gone(record, seconds)
      deadline = monotonic_now + seconds
      loop do
        return true unless process_identity_matches?(record)
        return false if monotonic_now >= deadline
        sleep 0.05
      end
    end

    def read_bounded_http_json(bind, port, path)
      socket = TCPSocket.new(bind, port)
      socket.write(
        "GET #{path} HTTP/1.1\r\n" \
        "Host: #{bind}:#{port}\r\n" \
        "Accept: application/json\r\n" \
        "Connection: close\r\n\r\n"
      )
      raw = +"".b
      loop do
        raw << socket.readpartial(512)
        raise StateError, "health response exceeds 8192 bytes" if raw.bytesize > 8192
      end
    rescue EOFError
      header, body = raw.split("\r\n\r\n", 2)
      raise StateError, "incomplete health response" unless header && body
      status_line = header.lines.first.to_s.strip
      match = /\AHTTP\/1\.[01] (\d{3})(?: .*)?\z/.match(status_line)
      raise StateError, "invalid health response status line" unless match
      [Integer(match[1], 10), JSON.parse(body)]
    ensure
      socket&.close
    end

    def monotonic_now
      Process.clock_gettime(Process::CLOCK_MONOTONIC)
    end
  end
end

exit TextStatsMcp::ManagedService.run(ARGV) if $PROGRAM_NAME == __FILE__
