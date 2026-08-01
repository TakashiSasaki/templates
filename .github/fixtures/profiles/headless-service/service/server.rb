#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "fileutils"
require "json"
require "net/http"
require "optparse"
require "timeout"
require "uri"
require "webrick"
require_relative "../src/text_stats"

module TextStatsService
  class ConfigurationError < StandardError; end

  class RequestError < StandardError
    attr_reader :status, :headers, :close_connection

    def initialize(status, message, headers: {}, close_connection: false)
      super(message)
      @status = status
      @headers = headers
      @close_connection = close_connection
    end
  end

  class Application
    MAX_BODY_BYTES = 64 * 1024
    MAX_CONCURRENT_API_REQUESTS = 1
    JSON_TYPE = "application/json; charset=utf-8"

    def initialize(port:, token:, diagnostic: $stderr)
      @port = port
      @token_digest = Digest::SHA256.digest(token)
      @diagnostic = diagnostic
      @admission_mutex = Mutex.new
      @active_api_requests = 0
      @ready = true
      hostnames = %w[127.0.0.1 localhost]
      @allowed_hosts = hostnames.flat_map do |hostname|
        port == 80 ? [hostname, "#{hostname}:80"] : ["#{hostname}:#{port}"]
      end.freeze
    end

    def mark_draining
      @admission_mutex.synchronize { @ready = false }
    end

    def service(request, response)
      apply_security_headers(response)
      authorize_host!(request)
      reject_browser_origin!(request)

      case [request.request_method, request.path]
      when ["GET", "/livez"]
        respond_json(response, 200, "ok" => true, "status" => "live")
      when ["GET", "/readyz"]
        ready = @admission_mutex.synchronize { @ready }
        respond_json(
          response,
          ready ? 200 : 503,
          "ok" => ready,
          "status" => ready ? "ready" : "draining"
        )
      when ["POST", "/v1/text-stats"]
        with_api_slot do
          authorize_bearer!(request)
          handle_stats(request, response)
        end
      else
        route_failure(request, response)
      end
    rescue WEBrick::HTTPStatus::RequestTimeout
      response["Connection"] = "close"
      respond_json(response, 408, "ok" => false, "error" => "request timed out")
    rescue RequestError => error
      error.headers.each { |name, value| response[name] = value }
      response["Connection"] = "close" if error.close_connection
      respond_json(response, error.status, "ok" => false, "error" => error.message)
    rescue StandardError => error
      @diagnostic.puts("service request failed: #{error.class}: #{error.message}")
      response["Connection"] = "close"
      respond_json(response, 500, "ok" => false, "error" => "internal server error")
    ensure
      @diagnostic.puts("service request #{request.request_method} #{request.path} -> #{response.status}")
    end

    private

    def authorize_host!(request)
      host = request["host"].to_s.downcase
      raise RequestError.new(403, "forbidden host", close_connection: true) unless @allowed_hosts.include?(host)
    end

    def reject_browser_origin!(request)
      return if request["origin"].to_s.empty?

      raise RequestError.new(403, "browser-origin requests are not supported", close_connection: true)
    end

    def authorize_bearer!(request)
      authorization = request["authorization"].to_s
      match = authorization.match(/\ABearer ([!-~]{1,512})\z/)
      supplied = match && match[1]
      valid = supplied && secure_digest_equal?(Digest::SHA256.digest(supplied), @token_digest)
      return if valid

      raise RequestError.new(
        401,
        "valid bearer token required",
        headers: { "WWW-Authenticate" => 'Bearer realm="text-stats-service"' },
        close_connection: true
      )
    end

    def secure_digest_equal?(left, right)
      difference = 0
      left.bytes.zip(right.bytes) { |a, b| difference |= a ^ b }
      difference.zero?
    end

    def with_api_slot
      admitted = @admission_mutex.synchronize do
        if !@ready || @active_api_requests >= MAX_CONCURRENT_API_REQUESTS
          false
        else
          @active_api_requests += 1
          true
        end
      end
      unless admitted
        raise RequestError.new(503, "service is busy or draining", close_connection: true)
      end

      yield
    ensure
      if admitted
        @admission_mutex.synchronize { @active_api_requests -= 1 }
      end
    end

    def handle_stats(request, response)
      content_type = request["content-type"].to_s.split(";", 2).first.to_s.strip.downcase
      unless content_type == "application/json"
        raise RequestError.new(415, "application/json is required", close_connection: true)
      end

      body = read_bounded_body(request)
      body.force_encoding(Encoding::UTF_8)
      unless body.valid_encoding?
        raise RequestError.new(400, "request body is not valid UTF-8", close_connection: true)
      end

      begin
        payload = JSON.parse(body)
      rescue JSON::ParserError
        raise RequestError.new(400, "invalid JSON request body", close_connection: true)
      end

      unless payload.is_a?(Hash) && payload.keys == ["text"] && payload["text"].is_a?(String)
        raise RequestError.new(
          422,
          "request must contain only one string field named text",
          close_connection: true
        )
      end

      respond_json(
        response,
        200,
        "contractVersion" => CONTRACT_VERSION,
        "ok" => true,
        "result" => TextStatsService.analyze(payload.fetch("text"))
      )
    end

    def read_bounded_body(request)
      content_length = request["content-length"]
      if content_length && /\A\d+\z/.match?(content_length) && content_length.to_i > MAX_BODY_BYTES
        raise RequestError.new(413, "request body exceeds 65536 bytes", close_connection: true)
      end

      body = +"".b
      request.body do |chunk|
        if body.bytesize + chunk.bytesize > MAX_BODY_BYTES
          raise RequestError.new(413, "request body exceeds 65536 bytes", close_connection: true)
        end
        body << chunk
      end
      body
    end

    def route_failure(request, response)
      known_path = ["/livez", "/readyz", "/v1/text-stats"].include?(request.path)
      if known_path
        response["Allow"] = request.path == "/v1/text-stats" ? "POST" : "GET"
        respond_json(response, 405, "ok" => false, "error" => "method not allowed")
      else
        respond_json(response, 404, "ok" => false, "error" => "not found")
      end
    end

    def apply_security_headers(response)
      response["Cache-Control"] = "no-store"
      response["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
      response["Referrer-Policy"] = "no-referrer"
      response["X-Content-Type-Options"] = "nosniff"
      response["X-Frame-Options"] = "DENY"
    end

    def respond_json(response, status, payload)
      response.status = status
      response["Content-Type"] = JSON_TYPE
      response.body = JSON.generate(payload)
    end
  end

  class ServerCommand
    DEFAULT_BIND = "127.0.0.1"
    DEFAULT_PORT = 4568
    DEFAULT_PID_FILE = "tmp/text-stats-service.pid"
    CONFIGURATION_EXIT = 78
    HEALTH_DEADLINE_SECONDS = 2
    HEALTH_RESPONSE_MAX_BYTES = 4096
    PID_RECORD_MAX_BYTES = 4096
    PID_RECORD_KEYS = %w[pid startTicks].freeze

    def self.run(argv, env: ENV, stdout: $stdout, stderr: $stderr)
      action = :start
      parser = OptionParser.new do |options|
        options.banner = "Usage: ruby service/server.rb [--health | --live | --stop]"
        options.on("--health", "Check service readiness") { action = :health }
        options.on("--live", "Check service liveness") { action = :live }
        options.on("--stop", "Stop the service using its PID record") { action = :stop }
        options.on("-h", "--help", "Show this help") do
          stdout.puts(options)
          return 0
        end
      end
      parser.parse!(argv)
      raise ConfigurationError, "unexpected arguments: #{argv.join(' ')}" unless argv.empty?

      configuration = configuration_from(env)
      case action
      when :health then health(configuration, "/readyz", "ready", stdout: stdout, stderr: stderr)
      when :live then health(configuration, "/livez", "live", stdout: stdout, stderr: stderr)
      when :stop then stop(configuration, stdout: stdout, stderr: stderr)
      else start(configuration, env: env, stderr: stderr)
      end
    rescue OptionParser::ParseError, ConfigurationError => error
      stderr.puts(error.message)
      CONFIGURATION_EXIT
    end

    def self.configuration_from(env)
      bind = env.fetch("TEXT_STATS_SERVICE_BIND", DEFAULT_BIND)
      unless bind == DEFAULT_BIND
        raise ConfigurationError, "TEXT_STATS_SERVICE_BIND must be 127.0.0.1"
      end

      raw_port = env.fetch("TEXT_STATS_SERVICE_PORT", DEFAULT_PORT.to_s)
      port = Integer(raw_port, 10)
      unless (0..65_535).cover?(port)
        raise ConfigurationError, "TEXT_STATS_SERVICE_PORT must be between 0 and 65535"
      end

      pid_file = File.expand_path(env.fetch("TEXT_STATS_SERVICE_PID_FILE", DEFAULT_PID_FILE), Dir.pwd)
      token_file_value = env["TEXT_STATS_SERVICE_TOKEN_FILE"]
      token_file = token_file_value && File.expand_path(token_file_value, Dir.pwd)
      { bind: bind, port: port, pid_file: pid_file, token_file: token_file }
    rescue ArgumentError
      raise ConfigurationError, "TEXT_STATS_SERVICE_PORT must be an integer between 0 and 65535"
    end

    def self.start(configuration, env:, stderr:)
      token = read_token(configuration.fetch(:token_file))
      logger = WEBrick::Log.new(stderr, WEBrick::Log::WARN)
      server = WEBrick::HTTPServer.new(
        BindAddress: configuration.fetch(:bind),
        Port: configuration.fetch(:port),
        AccessLog: [],
        Logger: logger,
        RequestTimeout: 2,
        KeepAliveTimeout: 1,
        MaxClients: 8
      )
      actual_port = server.listeners.fetch(0).addr[1]
      application = Application.new(port: actual_port, token: token, diagnostic: stderr)
      server.mount_proc("/") { |request, response| application.service(request, response) }

      pid_file = configuration.fetch(:pid_file)
      pid_record = current_pid_record
      write_pid_record(pid_file, pid_record)

      shutdown = proc do
        Thread.new do
          application.mark_draining
          server.shutdown
        end
      end
      Signal.trap("TERM", &shutdown)
      Signal.trap("INT", &shutdown)

      stderr.puts("text-stats service ready http://#{configuration.fetch(:bind)}:#{actual_port}/")
      server.start
      0
    rescue SystemCallError => error
      stderr.puts("unable to start headless service: #{error.message}")
      1
    ensure
      if defined?(pid_file) && pid_file && defined?(pid_record) && pid_record
        begin
          File.delete(pid_file) if read_pid_record(pid_file) == pid_record
        rescue ConfigurationError, SystemCallError
          nil
        end
      end
      stderr.puts("text-stats service stopped") if defined?(server) && server
    end

    def self.read_token(path)
      unless path
        raise ConfigurationError, "TEXT_STATS_SERVICE_TOKEN_FILE is required for service startup"
      end

      flags = File::RDONLY | File::NOFOLLOW
      raw = File.open(path, flags) do |file|
        stat = file.stat
        unless stat.file?
          raise ConfigurationError, "service token file must be a regular non-symlink file: #{path}"
        end
        unless stat.uid == Process.euid
          raise ConfigurationError, "service token file must be owned by the service user: #{path}"
        end
        mode = stat.mode & 0o777
        unless (mode & 0o077).zero?
          raise ConfigurationError, "service token file must not be accessible by group or other users: #{path}"
        end

        file.read(4097).to_s
      end
      raise ConfigurationError, "service token file exceeds 4096 bytes: #{path}" if raw.bytesize > 4096
      raw = raw.sub(/\r?\n\z/, "")
      unless /\A[!-~]{32,128}\z/.match?(raw)
        raise ConfigurationError, "service token must contain 32 to 128 visible ASCII characters"
      end
      raw
    rescue Errno::ELOOP
      raise ConfigurationError, "service token file must be a regular non-symlink file: #{path}"
    rescue SystemCallError => error
      raise ConfigurationError, "unable to read service token file #{path}: #{error.message}"
    end

    def self.health(configuration, path, expected_status, stdout:, stderr:)
      uri = URI("http://#{configuration.fetch(:bind)}:#{configuration.fetch(:port)}#{path}")
      request = Net::HTTP::Get.new(uri)
      request["Host"] = "#{configuration.fetch(:bind)}:#{configuration.fetch(:port)}"
      http = Net::HTTP.new(uri.host, uri.port, nil, nil, nil, nil)
      http.open_timeout = 1
      http.read_timeout = 1
      response_code = nil
      response_body = +"".b

      Timeout.timeout(HEALTH_DEADLINE_SECONDS) do
        http.start do |client|
          client.request(request) do |response|
            response_code = response.code
            response.read_body do |chunk|
              if response_body.bytesize + chunk.bytesize > HEALTH_RESPONSE_MAX_BYTES
                raise ConfigurationError,
                      "health response exceeds #{HEALTH_RESPONSE_MAX_BYTES} bytes"
              end
              response_body << chunk
            end
          end
        end
      end

      payload = JSON.parse(response_body)
      if response_code == "200" && payload == { "ok" => true, "status" => expected_status }
        stdout.puts("Headless service #{expected_status}")
        0
      else
        stderr.puts("Headless service #{expected_status} check failed with HTTP #{response_code}")
        1
      end
    rescue Timeout::Error
      stderr.puts("Headless service #{expected_status} check failed: overall deadline exceeded")
      1
    rescue StandardError => error
      stderr.puts("Headless service #{expected_status} check failed: #{error.message}")
      1
    end

    def self.stop(configuration, stdout:, stderr:)
      pid_file = configuration.fetch(:pid_file)
      unless File.exist?(pid_file) || File.symlink?(pid_file)
        stderr.puts("Headless service PID file not found: #{pid_file}")
        return 1
      end

      record = read_pid_record(pid_file)
      pid = record.fetch("pid")
      unless process_start_ticks(pid) == record.fetch("startTicks")
        stderr.puts("Headless service PID file is stale; refusing to signal process #{pid}")
        return 1
      end

      Process.kill("TERM", pid)
      stdout.puts("Sent TERM to headless service process #{pid}")
      0
    rescue ConfigurationError => error
      stderr.puts(error.message)
      1
    rescue Errno::ESRCH
      stderr.puts("Headless service process is not running")
      1
    rescue Errno::EPERM
      stderr.puts("Permission denied stopping headless service process")
      1
    end

    def self.current_pid_record
      start_ticks = process_start_ticks(Process.pid)
      raise ConfigurationError, "unable to read current process identity" unless start_ticks

      { "pid" => Process.pid, "startTicks" => start_ticks }
    end

    def self.write_pid_record(path, record)
      FileUtils.mkdir_p(File.dirname(path))
      if File.exist?(path) || File.symlink?(path)
        raise ConfigurationError, "Headless service PID file already exists: #{path}"
      end

      File.open(path, File::WRONLY | File::CREAT | File::EXCL, 0o600) do |file|
        file.write(JSON.generate(record))
        file.write("\n")
      end
    rescue Errno::EEXIST
      raise ConfigurationError, "Headless service PID file already exists: #{path}"
    rescue SystemCallError => error
      raise ConfigurationError, "unable to create headless service PID file #{path}: #{error.message}"
    end

    def self.read_pid_record(path)
      serialized = File.open(path, File::RDONLY | File::NOFOLLOW) do |file|
        stat = file.stat
        unless stat.file?
          raise ConfigurationError, "Headless service PID file must be a regular non-symlink file: #{path}"
        end
        unless stat.uid == Process.euid
          raise ConfigurationError, "Headless service PID file must be owned by the service user: #{path}"
        end
        mode = stat.mode & 0o777
        unless mode == 0o600
          raise ConfigurationError, "Headless service PID file must have mode 0600: #{path}"
        end

        contents = file.read(PID_RECORD_MAX_BYTES + 1).to_s
        if contents.bytesize > PID_RECORD_MAX_BYTES
          raise ConfigurationError, "Headless service PID file exceeds #{PID_RECORD_MAX_BYTES} bytes: #{path}"
        end
        contents
      end

      payload = JSON.parse(serialized)
      unless payload.is_a?(Hash) && payload.keys.sort == PID_RECORD_KEYS.sort &&
             payload["pid"].is_a?(Integer) && payload["pid"].positive? &&
             payload["startTicks"].is_a?(String) && /\A\d+\z/.match?(payload["startTicks"])
        raise ConfigurationError, "Headless service PID file is invalid: #{path}"
      end
      payload
    rescue Errno::ELOOP
      raise ConfigurationError, "Headless service PID file must be a regular non-symlink file: #{path}"
    rescue JSON::ParserError, EncodingError, SystemCallError
      raise ConfigurationError, "Headless service PID file is invalid: #{path}"
    end

    def self.process_start_ticks(pid)
      stat = File.read("/proc/#{pid}/stat", encoding: "UTF-8")
      closing_parenthesis = stat.rindex(")")
      return nil unless closing_parenthesis

      fields = stat[(closing_parenthesis + 2)..].to_s.split
      start_ticks = fields[19]
      /\A\d+\z/.match?(start_ticks.to_s) ? start_ticks : nil
    rescue SystemCallError, EncodingError
      nil
    end
  end
end

exit TextStatsService::ServerCommand.run(ARGV) if $PROGRAM_NAME == __FILE__
