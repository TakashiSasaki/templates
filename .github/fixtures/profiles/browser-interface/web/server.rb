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
      @allowed_hosts = ["127.0.0.1:#{port}", "localhost:#{port}"].freeze
      @allowed_origins = @allowed_hosts.map { |host| "http://#{host}" }.freeze
    end

    def service(request, response)
      apply_security_headers(response)
      authorize_host!(request)

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
        authorize_origin!(request)
        handle_stats(request, response)
      else
        route_failure(request, response)
      end
    rescue RequestError => error
      respond_json(response, error.status, "ok" => false, "error" => error.message)
    rescue StandardError => error
      @diagnostic.puts("web request failed: #{error.class}: #{error.message}")
      respond_json(response, 500, "ok" => false, "error" => "internal server error")
    ensure
      @diagnostic.puts("web request #{request.request_method} #{request.path} -> #{response.status}")
    end

    private

    def authorize_host!(request)
      host = request["host"].to_s.downcase
      raise RequestError.new(403, "forbidden host") unless @allowed_hosts.include?(host)
    end

    def authorize_origin!(request)
      origin = request["origin"].to_s
      raise RequestError.new(403, "same-origin browser request required") unless @allowed_origins.include?(origin)
    end

    def handle_stats(request, response)
      content_type = request["content-type"].to_s.split(";", 2).first.to_s.strip.downcase
      raise RequestError.new(415, "application/json is required") unless content_type == "application/json"

      body = request.body.to_s.b
      raise RequestError.new(413, "request body exceeds 65536 bytes") if body.bytesize > MAX_BODY_BYTES

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
      FileUtils.mkdir_p(File.dirname(pid_file))
      File.open(pid_file, "w:UTF-8") { |file| file.write("#{Process.pid}\n") }

      shutdown = proc { server.shutdown }
      Signal.trap("TERM", &shutdown)
      Signal.trap("INT", &shutdown)

      stderr.puts("text-stats web ready http://#{configuration.fetch(:bind)}:#{actual_port}/")
      server.start
      0
    rescue Errno::EADDRINUSE => error
      stderr.puts("unable to start Web UI: #{error.message}")
      1
    ensure
      if defined?(pid_file) && pid_file && File.file?(pid_file)
        begin
          File.delete(pid_file) if File.read(pid_file, encoding: "UTF-8").strip == Process.pid.to_s
        rescue Errno::ENOENT
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
      unless File.file?(pid_file)
        stderr.puts("Web UI PID file not found: #{pid_file}")
        return 1
      end

      pid = Integer(File.read(pid_file, encoding: "UTF-8").strip, 10)
      Process.kill("TERM", pid)
      stdout.puts("Sent TERM to Web UI process #{pid}")
      0
    rescue ArgumentError
      stderr.puts("Web UI PID file is invalid: #{pid_file}")
      1
    rescue Errno::ESRCH
      stderr.puts("Web UI process is not running")
      1
    rescue Errno::EPERM
      stderr.puts("Permission denied stopping Web UI process")
      1
    end

    private_class_method :configuration_from, :start, :health, :stop
  end
end

exit TextStatsWeb::ServerCommand.run(ARGV) if $PROGRAM_NAME == __FILE__
