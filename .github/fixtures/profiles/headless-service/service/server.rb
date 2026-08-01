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
    PID_RECORD_KEYS = %w[pid startTicks].freeze

    def self.run(argv, env: ENV, stdout: $stdout, stderr: $stderr)
      action = :start
      parser = OptionParser.new do |options|
        options.banner = "Usage: ruby service/server.rb [--health | --live | --stop]"
       options.on("--health", "Check service readiness") { action = :health }
      options.on("--live", "Check service liveliness") { action = :live }
      options.on(