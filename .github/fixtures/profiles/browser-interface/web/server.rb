#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "json"
require "net/http"
require "optparse"
require "uri"
require "webrick"
require_relative "../src/text_stats"

module TextStatsWeb
  class ConfigurationError < StandardError; end
  class RequestError < StandardError
    attr_reader :status

    def initialize(status, message)
      super(message)
      @status = status
    end
  end

  class Application
    MAX_BODY_BYTES = 64 * 1024
    JSON_TYPE = "application/json; charset=utf-8"
    HTML_TYPE = "text/html; charset=utf-8"
    JS_TYPE = "text/javascript; charset=utf-8"
    CSS_TYPE = "text/css; charset=utf-8"

    HTML = <<~HTML.freeze
      <!doctype html>
      <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Text statistics verification</title>
        <link rel="stylesheet" href="/app.css">
      </head>
      <body>
        <main>
          <h1>Text statistics verification</h1>
          <p>This loopback-only page computes byte, line, and word counts without retaining the submitted text.</p>
          <form id="stats-form">
            <label for="text">Text</label>
            <textarea id="text" name="text" required></textarea>
            <button type="submit">Compute</button>
          </form>
          <pre id="result" aria-live="polite"></pre>
        </main>
        <script src="/app.js" defer></script>
      </body>
      </html>
    HTML

    JAVASCRIPT = <<~JS.freeze
      "use strict";
      const form = document.getElementById("stats-form");
      const result = document.getElementById("result");
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        result.textContent = "Working...";
        try {
          const response = await fetch("/api/text-stats", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: document.getElementById("text").value })
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.error || "Request failed");
          result.textContent = JSON.stringify(payload.result, null, 2);
        } catch (error) {
          result.textContent = `Error: ${error.message}`;
        }
      });
    JS

    CSS = <<~CSS.freeze
      :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
      body { margin: 0; padding: 2rem; }
      main { max-width: 48rem; margin: 0 auto; }
      textarea { box-sizing: border-box; display: block; min-height: 12rem; width: 100%; margin: 0.5rem 0 1rem; }
      button { padding: 0.5rem 1rem; }
      pre { min-height: 5rem; padding: 1rem; border: 1px solid currentColor; overflow: auto; }
    CSS

    def initialize(port:, diagnostic: $stderr)
      @port = port
      @diagnostic = diagnostic
      @allowed_hostnames = %w[127.0.0.1 localhost].freeze
    end

    def service(request, response)
      apply_security_headers(response)
      request_origin = authorize_host!(request)

      case [request.request_method, request.path]
      when ["GET", "/"]
        respond(response, 200, HTML_TYPE, HTML)
      when ["GET", "/app.js"]
        respond(response, 200, JS_TYPE, JAVASCRIPT)
      when ["GET", "/app.css"]
        respond(response, 200, CSS_TYPE, CSS)
      when ["GET", "/healthz"]
        respond_json(response, 200, "ok" => true, "interface" => "web")
      when ["POST", "/api/text-stats"]
        authorize_origin!(request, request_origin)
        handle_stats(request, response)
      else
        route_failure(request, response)
      end
    rescue RequestError => error
      response["Connection"] = "close" if error.status == 413
      respond_json(response, error.status, "ok" => false, "error" => error.message)
    rescue StandardError => error
      @diagnostic.puts("web request failed: #{error.class}: #{error.message}")
      respond_json(response, 500, "ok" => false, "error" => "internal server error")
    ensure
      @diagnostic.puts("web request #{request.request_method} #{request.path} -> #{response.status}")
    end

    private

    def authorize_host!(request)
      authority = parse_http_authority(request["host"].to_s)
      unless authority && @allowed_hostnames.include?(authority.fetch(0)) && authority.fetch(1) == @port
        raise RequestError.new(403, "forbidden host")
      end

      authority
    end

    def authorize_origin!(request, request_origin)
      origin = parse_http_origin(request["origin"].to_s)
      unless origin == request_origin
        raise RequestError.new(403, "same-origin browser request required")
      end
    end

    def parse_http_authority(value)
      uri = URI.parse("http://#{value}")
      return nil unless uri.scheme == "http" && uri.userinfo.nil? && uri.host &&
                        uri.path.empty? && uri.query.nil? && uri.fragment.nil?

      [uri.host.downcase, uri.port]
    rescue URI::InvalidURIError
      nil
    end

    def parse_http_origin(value)
      uri = URI.parse(value)
      return nil unless uri.scheme == "http" && uri.userinfo.nil? && uri.host &&
                        uri.path.empty? && uri.query.nil? && uri.fragment.nil?

      [uri.host.downcase, uri.port]
    rescue URI::InvalidURIError
      nil
    end

    def handle_stats(request, response)
      content_type = request["content-type"].to_s.split(";", 2).first.to_s.strip.downcase
      raise RequestError.new(415, "application/json is required") unless content_type == "application/json"

      body = read_bounded_body(request)
      body.force_encoding(Encoding::UTF_8)
      raise RequestError.new(400, "request body is not valid UTF-8") unless body.valid_encoding?

      begin
        payload = JSON.parse(body)
      rescue JSON::ParserError
        raise RequestError.new(400, "invalid JSON request body")
      end

      unless payload.is_a?(Hash) && payload.keys == ["text"] && payload["text"].is_a?(String)
        raise RequestError.new(422, "request must contain only one string field named text")
      end

      respond_json(
        response,
        200,
        "contractVersion" => CONTRACT_VERSION,
        "ok" => true,
        "result" => TextStatsWeb.analyze(payload.fetch("text"))
      )
    end

    def read_bounded_body(request)
      content_length = request["content-length"]
      if content_length && /\A\d+\z/.match?(content_length) && content_length.to_i > MAX_BODY_BYTES
        raise RequestError.new(413, "request body exceeds 65536 bytes")
      end

      body = +"".b
      request.body do |chunk|
        if body.bytesize + chunk.bytesize > MAX_BODY_BYTES
          raise RequestError.new(413, "request body exceeds 65536 bytes")
        end

        body << chunk
      end
      body
    end

    def route_failure(request, response)
      known_path = ["/", "/app.js", "/app.css", "/healthz", "/api/text-stats"].include?(request.path)
      if known_path
        response["Allow"] = request.path == "/api/text-stats" ? "POST" : "GET"
        respond_json(response, 405, "ok" => false, "error" => "method not allowed")
      else
        respond_json(response, 404, "ok" => false, "error" => "not found")
      end
    end

    def apply_security_headers(response)
      response["Cache-Control"] = "no-store"
      response["Content-Security-Policy"] = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
      response["Referrer-Policy"] = "no-referrer"
      response["X-Content-Type-Options"] = "nosniff"
      response["X-Frame-Options"] = "DENY"
    end

    def respond_json(response, status, payload)
      respond(response, status, JSON_TYPE, JSON.generate(payload))
    end

    def respond(response, status, content_type, body)
      response.status = status
      response["Content-Type"] = content_type
      response.body = body
    end
  end

  class ServerCommand
    DEFAULT_BIND = "127.0.0.1"
    DEFAULT_PORT = 4567
    DEFAULT_PID_FILE = "tmp/text-stats-web.pid"
    DISABLED_EXIT = 78
    PID_RECORD_KEYS = %w[pid startTicks].freeze

    def self.run(argv, env: ENV, stdout: $stdout, stderr: $stderr)
      action = :start
      parser = OptionParser.new do |options|
        options.banner = "Usage: ruby web/server.rb [--health | --stop]"
        options.on("--health", "Check Web UI readiness") { action = :health }
        options.on("--stop", "Stop the Web UI using its PID file") { action = :stop }
        options.on("-h", "--help", "Show this help") do
          stdout.puts(options)
          return 0
        end
      end
      parser.parse!(argv)
      raise ConfigurationError, "unexpected arguments: #{argv.join(' ')}" unless argv.empty?

      configuration = configuration_from(env)
      case action
      when :health then health(configuration, stdout: stdout, stderr: stderr)
      when :stop then stop(configuration, stdout: stdout, stderr: stderr)
      else start(configuration, env: env, stderr: stderr)
      end
    rescue OptionParser::ParseError, ConfigurationError => error
      stderr.puts(error.message)
      DISABLED_EXIT
    end

    def self.configuration_from(env)
      bind = env.fetch("TEXT_STATS_WEB_BIND", DEFAULT_BIND)
      raise ConfigurationError, "TEXT_STATS_WEB_BIND must be 127.0.0.1" unless bind == DEFAULT_BIND

      raw_port = env.fetch("TEXT_STATS_WEB_PORT", DEFAULT_PORT.to_s)
      port = Integer(raw_port, 10)
      raise ConfigurationError, "TEXT_STATS_WEB_PORT must be between 0 and 65535" unless (0..65_535).cover?(port)

      pid_file = File.expand_path(env.fetch("TEXT_STATS_WEB_PID_FILE", DEFAULT_PID_FILE), Dir.pwd)
      { bind: bind, port: port, pid_file: pid_file }
    rescue ArgumentError
      raise ConfigurationError, "TEXT_STATS_WEB_PORT must be an integer between 0 and 65535"
    end

    def self.start(configuration, env:, stderr:)
      unless env["TEXT_STATS_WEB_ENABLED"] == "1"
        raise ConfigurationError, "Web UI is disabled; set TEXT_STATS_WEB_ENABLED=1 to start it"
      end

      logger = WEBrick::Log.new(stderr, WEBrick::Log::WARN)
      server = WEBrick::HTTPServer.new(
        BindAddress: configuration.fetch(:bind),
        Port: configuration.fetch(:port),
        AccessLog: [],
        Logger: logger
      )
      actual_port = server.listeners.fetch(0).addr[1]
      application = Application.new(port: actual_port, diagnostic: stderr)
      server.mount_proc("/") { |request, response| application.service(request, response) }

      pid_file = configuration.fetch(:pid_file)
      pid_record = current_pid_record
      write_pid_record(pid_file, pid_record)

      shutdown = proc { server.shutdown }
      Signal.trap("TERM", &shutdown)
      Signal.trap("INT", &shutdown)

      stderr.puts("text-stats web ready http://#{configuration.fetch(:bind)}:#{actual_port}/")
      server.start
      0
    rescue SystemCallError => error
      stderr.puts("unable to start Web UI: #{error.message}")
      1
    ensure
      if defined?(pid_file) && pid_file && defined?(pid_record) && pid_record
        begin
          File.delete(pid_file) if read_pid_record(pid_file) == pid_record
        rescue ConfigurationError, SystemCallError
          nil
        end
      end
      stderr.puts("text-stats web stopped") if defined?(server) && server
    end

    def self.health(configuration, stdout:, stderr:)
      uri = URI("http://#{configuration.fetch(:bind)}:#{configuration.fetch(:port)}/healthz")
      request = Net::HTTP::Get.new(uri)
      request["Host"] = "#{configuration.fetch(:bind)}:#{configuration.fetch(:port)}"
      http = Net::HTTP.new(uri.host, uri.port, nil, nil, nil, nil)
      http.open_timeout = 1
      http.read_timeout = 1
      response = http.start { |client| client.request(request) }
      if response.code == "200" && JSON.parse(response.body) == { "ok" => true, "interface" => "web" }
        stdout.puts("Web UI ready")
        0
      else
        stderr.puts("Web UI readiness check failed with HTTP #{response.code}")
        1
      end
    rescue StandardError => error
      stderr.puts("Web UI readiness check failed: #{error.message}")
      1
    end

    def self.stop(configuration, stdout:, stderr:)
      pid_file = configuration.fetch(:pid_file)
      unless File.exist?(pid_file) || File.symlink?(pid_file)
        stderr.puts("Web UI PID file not found: #{pid_file}")
        return 1
      end

      record = read_pid_record(pid_file)
      pid = record.fetch("pid")
      unless process_start_ticks(pid) == record.fetch("startTicks")
        stderr.puts("Web UI PID file is stale; refusing to signal process #{pid}")
        return 1
      end

      Process.kill("TERM", pid)
      stdout.puts("Sent TERM to Web UI process #{pid}")
      0
    rescue ConfigurationError => error
      stderr.puts(error.message)
      1
    rescue Errno::ESRCH
      stderr.puts("Web UI process is not running")
      1
    rescue Errno::EPERM
      stderr.puts("Permission denied stopping Web UI process")
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
        raise ConfigurationError, "Web UI PID file already exists: #{path}"
      end

      File.open(path, File::WRONLY | File::CREAT | File::EXCL, 0o600) do |file|
        file.write(JSON.generate(record))
        file.write("\n")
      end
    rescue Errno::EEXIST
      raise ConfigurationError, "Web UI PID file already exists: #{path}"
    rescue SystemCallError => error
      raise ConfigurationError, "unable to create Web UI PID file #{path}: #{error.message}"
    end

    def self.read_pid_record(path)
      if File.symlink?(path) || !File.file?(path)
        raise ConfigurationError, "Web UI PID file must be a regular non-symlink file: #{path}"
      end

      payload = JSON.parse(File.read(path, encoding: "UTF-8"))
      unless payload.is_a?(Hash) && payload.keys.sort == PID_RECORD_KEYS.sort &&
             payload["pid"].is_a?(Integer) && payload["pid"].positive? &&
             payload["startTicks"].is_a?(String) && /\A\d+\z/.match?(payload["startTicks"])
        raise ConfigurationError, "Web UI PID file is invalid: #{path}"
      end

      payload
    rescue JSON::ParserError, EncodingError, SystemCallError
      raise ConfigurationError, "Web UI PID file is invalid: #{path}"
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

    private_class_method :configuration_from, :start, :health, :stop,
                         :current_pid_record, :write_pid_record, :read_pid_record,
                         :process_start_ticks
  end
end

exit TextStatsWeb::ServerCommand.run(ARGV) if $PROGRAM_NAME == __FILE__
