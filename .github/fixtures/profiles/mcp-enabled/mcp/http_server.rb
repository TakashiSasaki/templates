# frozen_string_literal: true

require "json"
require "openssl"
require "rack"
require "rackup/handler/webrick"
require "uri"
require_relative "server_factory"

module TextStatsMcp
  HTTP_BIND = "127.0.0.1"
  HTTP_DEFAULT_PORT = 4570
  HTTP_MAX_REQUEST_BYTES = 65_536
  HTTP_MAX_SESSIONS = 16
  HTTP_SESSION_IDLE_TIMEOUT = 300

  class ConfigurationError < StandardError; end

  class ShutdownCoordinator
    def initialize
      @server = nil
      @requested = false
    end

    def request
      @requested = true
      schedule_shutdown(@server)
    end

    def attach(server)
      @server = server
      schedule_shutdown(server) if @requested
      @requested
    end

    private

    def schedule_shutdown(server)
      return unless server

      Thread.new { server.shutdown }
    end
  end

  class HttpApplication
    def initialize(transport:, host:, port:, token_matcher:)
      @transport = transport
      @host = host.downcase
      @port = port
      @token_matcher = token_matcher
    end

    def call(env)
      request = Rack::Request.new(env)
      security_error = validate_request_authority(request)
      return security_error if security_error

      case request.path_info
      when "/readyz"
        return method_not_allowed("GET") unless request.get?

        json_response(200, status: "ready")
      when "/mcp"
        return method_not_allowed("POST, DELETE") unless request.post? || request.delete?
        return unauthorized_response unless @token_matcher.call(request)

        @transport.call(env)
      else
        json_response(404, error: "not found")
      end
    end

    private

    def validate_request_authority(request)
      host = request.get_header("HTTP_HOST")
      return forbidden_response("invalid Host header") unless canonical_host?(host)

      origin = request.get_header("HTTP_ORIGIN")
      return if origin.nil? || canonical_origin?(origin)

      forbidden_response("invalid Origin header")
    end

    def canonical_host?(value)
      return false unless value

      normalized = value.downcase
      return [@host, "#{@host}:80"].include?(normalized) if @port == 80

      normalized == "#{@host}:#{@port}"
    end

    def canonical_origin?(value)
      parsed = URI.parse(value)
      parsed.scheme&.casecmp?("http") &&
        parsed.host&.casecmp?(@host) &&
        parsed.port == @port &&
        parsed.userinfo.nil? &&
        parsed.path.to_s.empty? &&
        parsed.query.nil? &&
        parsed.fragment.nil?
    rescue URI::InvalidURIError
      false
    end

    def unauthorized_response
      [
        401,
        {
          "content-type" => "application/json",
          "cache-control" => "no-store",
          "www-authenticate" => "Bearer"
        },
        [JSON.generate(error: "unauthorized")]
      ]
    end

    def forbidden_response(message)
      json_response(403, error: message)
    end

    def method_not_allowed(allowed)
      status, headers, body = json_response(405, error: "method not allowed")
      headers["allow"] = allowed
      [status, headers, body]
    end

    def json_response(status, payload)
      [
        status,
        { "content-type" => "application/json", "cache-control" => "no-store" },
        [JSON.generate(payload)]
      ]
    end
  end

  module_function

  def load_http_configuration
    bind = ENV.fetch("TEXT_STATS_MCP_HTTP_BIND", HTTP_BIND)
    raise ConfigurationError, "TEXT_STATS_MCP_HTTP_BIND must be 127.0.0.1" unless bind == HTTP_BIND

    port_text = ENV.fetch("TEXT_STATS_MCP_HTTP_PORT", HTTP_DEFAULT_PORT.to_s)
    port = Integer(port_text, 10)
    raise ConfigurationError, "TEXT_STATS_MCP_HTTP_PORT must be between 1 and 65535" unless (1..65_535).cover?(port)

    token = ENV["TEXT_STATS_MCP_HTTP_TOKEN"]
    unless token&.match?(/\A[!-~]{32,128}\z/)
      raise ConfigurationError,
            "TEXT_STATS_MCP_HTTP_TOKEN must contain 32 to 128 non-whitespace printable ASCII characters"
    end

    [bind, port, token]
  rescue ArgumentError
    raise ConfigurationError, "TEXT_STATS_MCP_HTTP_PORT must be a base-10 integer between 1 and 65535"
  end

  def session_idle_timeout
    return HTTP_SESSION_IDLE_TIMEOUT unless ENV["TEXT_STATS_MCP_TEST_MODE"] == "1"

    timeout = Integer(ENV.fetch("TEXT_STATS_MCP_TEST_SESSION_IDLE_TIMEOUT", HTTP_SESSION_IDLE_TIMEOUT.to_s), 10)
    raise ConfigurationError, "test session idle timeout must be positive" unless timeout.positive?

    timeout
  rescue ArgumentError
    raise ConfigurationError, "test session idle timeout must be a positive base-10 integer"
  end

  def build_token_matcher(expected_token)
    lambda do |request|
      authorization = request.get_header("HTTP_AUTHORIZATION").to_s
      next false unless authorization.start_with?("Bearer ")

      supplied = authorization.delete_prefix("Bearer ")
      supplied.bytesize == expected_token.bytesize &&
        OpenSSL.fixed_length_secure_compare(supplied, expected_token)
    rescue ArgumentError
      false
    end
  end

  def endpoint_origin(host, port)
    port == 80 ? "http://#{host}" : "http://#{host}:#{port}"
  end

  def run_http_server
    $stderr.sync = true
    transport = nil
    server = nil
    exit_status = 0

    begin
      bind, port, token = load_http_configuration
      origin = endpoint_origin(bind, port)
      token_matcher = build_token_matcher(token)

      transport = MCP::Server::Transports::StreamableHTTPTransport.new(
        build_server,
        enable_json_response: true,
        session_idle_timeout: session_idle_timeout,
        max_sessions: HTTP_MAX_SESSIONS,
        dns_rebinding_protection: false,
        session_request_validator: ->(request, _session_id) { token_matcher.call(request) },
        max_request_bytes: HTTP_MAX_REQUEST_BYTES
      )
      application = HttpApplication.new(
        transport: transport,
        host: bind,
        port: port,
        token_matcher: token_matcher
      )
      shutdown = ShutdownCoordinator.new

      %w[TERM INT].each do |signal|
        Signal.trap(signal) { shutdown.request }
      end

      warn "text-stats MCP HTTP server starting on #{origin}"
      Rackup::Handler::WEBrick.run(
        application,
        Host: bind,
        Port: port,
        AccessLog: [],
        Logger: WEBrick::Log.new($stderr, WEBrick::Log::WARN)
      ) do |instance|
        server = instance
        if shutdown.attach(instance)
          warn "text-stats MCP HTTP shutdown requested during startup"
        else
          warn "text-stats MCP HTTP server ready"
        end
      end
    rescue ConfigurationError, SystemCallError => error
      warn "text-stats MCP HTTP server failed: #{error.message}"
      exit_status = 1
    ensure
      transport&.close
      warn "text-stats MCP HTTP server stopped" if server
    end

    exit_status
  end
end

exit TextStatsMcp.run_http_server if $PROGRAM_NAME == __FILE__
