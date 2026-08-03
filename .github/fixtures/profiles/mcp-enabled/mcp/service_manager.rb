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
    PID_RECORD_KEYS = %w[pid readinessNonce startTicks].freeze
    NONCE_PATTERN = /\A[0-9a-f]{64}\z/

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
      with_lifecycle_lock(configuration) do |lock_identity|
        case action
        when "start"
          start(configuration, env: env, lock_identity: lock_identity, stdout: stdout, stderr: stderr)
        when "stop"
          stop(configuration, stdout: stdout, stderr: stderr)
        when "restart"
          stop_status = stop(configuration, stdout: stdout, stderr: stderr)
          next stop_status unless stop_status.zero?

          start(configuration, env: env, lock_identity: lock_identity, stdout: stdout, stderr: stderr)
        when "ready"
          probe(configuration, "/readyz", "ready", stdout: stdout, stderr: stderr)
        when "live"
          probe(configuration, "/livez", "live", stdout: stdout, stderr: stderr)
        end
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
      lock_file = "#{pid_file}.lock"
      token_file_value = env["TEXT_STATS_MCP_HTTP_TOKEN_FILE"]
      token_file = token_file_value && File.expand_path(token_file_value, ROOT)

      named_paths = {
        "managed PID record" => pid_file,
        "managed log" => log_file,
        "managed lifecycle lock" => lock_file
      }
      named_paths["MCP HTTP token file"] = token_file if token_file
      duplicate = named_paths.group_by { |_name, path| path }.find { |_path, entries| entries.length > 1 }
      if duplicate
        names = duplicate.fetch(1).map(&:first).join(" and ")
        raise ConfigurationError, "#{names} must use different paths"
      end

      {
        bind: bind,
        port: port,
        pid_file: pid_file,
        log_file: log_file,
        lock_file: lock_file,
        token_file: token_file
      }
    rescue ArgumentError
      raise ConfigurationError, "TEXT_STATS_MCP_HTTP_PORT must be a base-10 integer between 1 and 65535"
    end

    def with_lifecycle_lock(configuration)
      path = configuration.fetch(:lock_file)
      directory = ensure_private_directory(File.dirname(path))
      path = File.join(directory, File.basename(path))
      file = open_or_create_runtime_file(path, File::RDWR, "managed MCP HTTP lifecycle lock")
      file.flock(File::LOCK_EX)
      stat = file.stat
      yield([stat.dev, stat.ino])
    ensure
      begin
        file&.flock(File::LOCK_UN)
      rescue IOError, SystemCallError
        nil
      end
      file&.close
    end

    def start(configuration, env:, lock_identity:, stdout:, stderr:)
      pid = nil
      record = nil
      log = nil
      token_identity = validate_token_file(configuration.fetch(:token_file))
      reject_identity_alias(
        token_identity,
        lock_identity,
        "MCP HTTP token file",
        "managed MCP HTTP lifecycle lock"
      )
      clear_stale_record(configuration.fetch(:pid_file), stdout: stdout)
      log = open_private_log(
        configuration.fetch(:log_file),
        forbidden_identities: {
          "MCP HTTP token file" => token_identity,
          "managed MCP HTTP lifecycle lock" => lock_identity
        }
      )
      nonce = SecureRandom.hex(32)
      child_env = {
        "TEXT_STATS_MCP_HTTP_BIND" => configuration.fetch(:bind),
        "TEXT_STATS_MCP_HTTP_PORT" => configuration.fetch(:port).to_s,
        "TEXT_STATS_MCP_HTTP_TOKEN" => nil,
        "TEXT_STATS_MCP_HTTP_TOKEN_FILE" => configuration.fetch(:token_file),
        "TEXT_STATS_MCP_MANAGED_INSTANCE_NONCE" => nonce,
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
      record = {
        "pid" => pid,
        "startTicks" => wait_for_start_ticks(pid),
        "readinessNonce" => nonce
      }
      write_pid_record(configuration.fetch(:pid_file), record)
      Process.detach(pid)
      wait_until_ready(configuration, record)
      stdout.puts("Managed MCP HTTP service started with PID #{pid}")
      0
    rescue ConfigurationError, StateError, SystemCallError => error
      cleanup_complete = if record
                           cleanup_recorded_start_failure(configuration.fetch(:pid_file), record)
                         elsif pid
                           terminate_spawned_process(pid)
                         else
                           true
                         end

      message = "unable to start managed MCP HTTP service: #{error.message}"
      if record && !cleanup_complete
        message = "#{message}; managed child remains live after bounded cleanup and its PID record was retained"
      elsif pid && !record && !cleanup_complete
        message = "#{message}; spawned child remains live after bounded cleanup"
      end
      stderr.puts(message)
      error.is_a?(ConfigurationError) && cleanup_complete ? CONFIGURATION_EXIT : 1
    ensure
      log&.close
    end

    def cleanup_recorded_start_failure(path, record)
      return false unless terminate_recorded_process(record)

      remove_pid_record_if_same(path, record)
      true
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

      unless terminate_recorded_process(record)
        raise StateError, "managed MCP HTTP service did not stop after bounded escalation; PID record retained"
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
      expected_payload = {
        "status" => expected_status,
        "instanceNonce" => record.fetch("readinessNonce")
      }
      unless status == 200 && payload == expected_payload
        raise StateError, "managed MCP HTTP #{expected_status} probe did not identify the recorded instance"
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
      expected_payload = {
        "status" => "ready",
        "instanceNonce" => record.fetch("readinessNonce")
      }
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
          return if status == 200 && payload == expected_payload
        rescue Timeout::Error, SystemCallError, JSON::ParserError, StateError
          nil
        end

        raise StateError, "managed MCP HTTP readiness deadline exceeded" if monotonic_now >= deadline

        sleep 0.05
      end
    end

    def validate_token_file(path)
      raise ConfigurationError, "TEXT_STATS_MCP_HTTP_TOKEN_FILE is required for managed startup" unless path

      raw, identity = open_private_file(path, "MCP HTTP token file") do |file|
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
      identity
    end

    def open_private_log(path, forbidden_identities: {})
      directory = ensure_private_directory(File.dirname(path))
      path = File.join(directory, File.basename(path))
      file = open_or_create_runtime_file(
        path,
        File::WRONLY | File::APPEND,
        "managed MCP HTTP log"
      )
      stat = file.stat
      identity = [stat.dev, stat.ino]
      forbidden_identities.each do |description, forbidden_identity|
        reject_identity_alias(identity, forbidden_identity, "managed MCP HTTP log", description)
      end
      file.sync = true
      file
    rescue ConfigurationError
      file&.close
      raise
    end

    def open_or_create_runtime_file(path, access_flags, description)
      file = nil
      begin
        file = File.open(
          path,
          access_flags | File::CREAT | File::EXCL | File::NOFOLLOW,
          0o600
        )
        file.chmod(0o600)
      rescue Errno::EEXIST
        file = File.open(path, access_flags | File::NOFOLLOW)
      rescue Errno::ELOOP
        raise ConfigurationError, "#{description} must not be a symbolic link: #{path}"
      end
      validate_private_stat(file.stat, path, description, exact_mode: 0o600)
      file
    rescue ConfigurationError
      file&.close
      raise
    rescue SystemCallError => error
      file&.close
      raise ConfigurationError, "unable to open #{description.downcase} #{path}: #{error.message}"
    end

    def open_private_file(path, description, missing: :configuration)
      flags = File::RDONLY | File::NOFOLLOW | File::NONBLOCK
      File.open(path, flags) do |file|
        stat = file.stat
        validate_private_stat(stat, path, description)
        return [yield(file), [stat.dev, stat.ino]]
      end
    rescue Errno::ELOOP
      raise ConfigurationError, "#{description} must not be a symbolic link: #{path}"
    rescue Errno::ENOENT
      raise if missing == :raw

      raise ConfigurationError, "#{description} does not exist: #{path}"
    rescue ConfigurationError
      raise
    rescue SystemCallError => error
      raise ConfigurationError, "unable to read #{description.downcase} #{path}: #{error.message}"
    end

    def validate_private_stat(stat, path, description, exact_mode: nil)
      raise ConfigurationError, "#{description} must be a regular file: #{path}" unless stat.file?
      raise ConfigurationError, "#{description} must be owned by the service user: #{path}" unless stat.uid == Process.euid
      unless (stat.mode & 0o077).zero?
        raise ConfigurationError, "#{description} must not be accessible by group or other users: #{path}"
      end
      if exact_mode && (stat.mode & 0o777) != exact_mode
        raise ConfigurationError, "#{description} must have mode #{format('%04o', exact_mode)}: #{path}"
      end
    end

    def reject_identity_alias(first, second, first_description, second_description)
      return unless first && second && first == second

      raise ConfigurationError, "#{first_description} and #{second_description} must not reference the same file"
    end

    def clear_stale_record(path, stdout:)
      record = read_pid_record(path, missing: :nil)
      return unless record
      raise StateError, "managed MCP HTTP service is already running with PID #{record.fetch("pid")}" if process_identity_matches?(record)

      remove_pid_record_if_same(path, record)
      stdout.puts("Removed stale managed MCP HTTP PID record")
    end

    def read_pid_record_entry(path, missing: :error)
      raw, identity = open_private_file(path, "managed MCP HTTP PID record", missing: :raw) do |file|
        content = file.read(PID_RECORD_MAX_BYTES + 1).to_s
        if content.bytesize > PID_RECORD_MAX_BYTES
          raise ConfigurationError, "managed MCP HTTP PID record exceeds #{PID_RECORD_MAX_BYTES} bytes: #{path}"
        end
        content
      end
      payload = JSON.parse(raw)
      unless payload.is_a?(Hash) && payload.keys.sort == PID_RECORD_KEYS.sort &&
             payload["pid"].is_a?(Integer) && payload["pid"].positive? &&
             payload["startTicks"].is_a?(String) && /\A\d+\z/.match?(payload["startTicks"]) &&
             payload["readinessNonce"].is_a?(String) && NONCE_PATTERN.match?(payload["readinessNonce"])
        raise ConfigurationError, "managed MCP HTTP PID record has an invalid schema: #{path}"
      end
      { record: payload, identity: identity }
    rescue Errno::ENOENT
      return nil if missing == :nil
      raise ConfigurationError, "managed MCP HTTP PID record does not exist: #{path}"
    rescue JSON::ParserError
      raise ConfigurationError, "managed MCP HTTP PID record is not valid JSON: #{path}"
    end

    def read_pid_record(path, missing: :error)
      read_pid_record_entry(path, missing: missing)&.fetch(:record)
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
        validate_private_stat(
          file.stat,
          temporary_path,
          "managed MCP HTTP PID staging file",
          exact_mode: 0o600
        )
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
      components = expanded.split(File::SEPARATOR).reject(&:empty?)
      components.each_with_index do |component, index|
        current = File.join(current, component)
        created = false
        begin
          stat = File.lstat(current)
        rescue Errno::ENOENT
          begin
            Dir.mkdir(current, 0o700)
            created = true
          rescue Errno::EEXIST
            nil
          end
          File.chmod(0o700, current) if created
          stat = File.lstat(current)
        end
        if stat.symlink? || !stat.directory?
          raise ConfigurationError, "managed runtime path component must be a non-symlink directory: #{current}"
        end

        final = index == components.length - 1
        if created
          unless stat.uid == Process.euid && (stat.mode & 0o777) == 0o700
            raise ConfigurationError, "managed runtime directory failed owner-only validation: #{current}"
          end
        elsif final
          unless stat.uid == Process.euid
            raise ConfigurationError, "managed runtime directory must be owned by the service user: #{current}"
          end
          unless (stat.mode & 0o022).zero?
            raise ConfigurationError, "managed runtime directory must not be writable by group or other users: #{current}"
          end
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
      entry = read_pid_record_entry(path, missing: :nil)
      return unless entry && entry.fetch(:record) == record

      current = File.lstat(path)
      return unless current.file? && [current.dev, current.ino] == entry.fetch(:identity)

      File.unlink(path)
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
      return true unless record && record["startTicks"] && process_identity_matches?(record)
      pid = record.fetch("pid")
      signal_group("TERM", pid)
      return true if wait_until_identity_gone(record, TERM_GRACE_SECONDS)

      signal_group("KILL", pid)
      wait_until_identity_gone(record, KILL_GRACE_SECONDS)
    end

    def terminate_spawned_process(pid)
      signal_group("TERM", pid)
      deadline = monotonic_now + TERM_GRACE_SECONDS
      while process_exists?(pid) && monotonic_now < deadline
        sleep 0.05
      end
      if process_exists?(pid)
        signal_group("KILL", pid)
        kill_deadline = monotonic_now + KILL_GRACE_SECONDS
        while process_exists?(pid) && monotonic_now < kill_deadline
          sleep 0.05
        end
      end
      !process_exists?(pid)
    end

    def process_exists?(pid)
      Process.kill(0, pid)
      state, = proc_identity(pid)
      state != "Z"
    rescue Errno::ESRCH, Errno::ENOENT, StateError
      false
    end

    def signal_group(signal, pid)
      Process.kill(signal, -pid)
    rescue Errno::ESRCH
      begin
        Process.kill(signal, pid)
      rescue Errno::ESRCH
        nil
      end
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
