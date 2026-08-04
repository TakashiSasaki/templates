# frozen_string_literal: true

require "json"
require "openssl"
require "rack"
require "rackup/handler/webrick"
require "socket"
require "uri"
require_relative "server_factory"

module TextStatsMcpSystemd
  HTTP_BIND = "127.0.0.1"
  HTTP_DEFAULT_PORT = 4572
  HTTP_MAX_REQUEST_BYTES = 65_536
  HTTP_MAX_SESSIONS = 16
  HTTP_SESSION_IDLE_TIMEOUT = 300
  TOKEN_FILE_MAX_BYTES = 4096
  SYSTEMD_CREDENTIAL_NAME = "text-stats-mcp-token"

  class ConfigurationError < StandardError; end

  class BoundedHTTPRequest < WEBrick::HTTPRequest
    def preload_bounded_body!
      return if @bounded_body_preloaded

      body
      @bounded_body_preloaded = true
    end

    def body(&block)
      unless @bounded_body_preloaded
        return super
      end

      block&.call(@body) unless @body.empty?
      @body.empty? ? nil : @body
    end

    def enforce_declared_body_limit!
      content_length = self["content-length"]
      return unless content_length && content_length.to_i > request_body_limit

      raise WEBrick::HTTPStatus::RequestEntityTooLarge,
            "request body exceeds #{request_body_limit} bytes"
    end

    private

    def read_body(socket, block)
      enforce_declared_body_limit!
      @bounded_body_bytes ||= 0
      bounded_block = lambda do |chunk|
        @bounded_body_bytes += chunk.bytesize
        if @bounded_body_bytes > request_body_limit
          raise WEBrick::HTTPStatus::RequestEntityTooLarge,
                "request body exceeds #{request_body_limit} bytes"
        end
        block.call(chunk)
      end
      super(socket, bounded_block)
    end

    def request_body_limit
      @config.fetch(:RequestBodyLimit)
    end
  end

  class BoundedHTTPServer < WEBrick::HTTPServer
    def create_request(config)
      BoundedHTTPRequest.new(config)
    end
  end

  class SystemdNotifier
    def initialize(socket_name = ENV["NOTIFY_SOCKET"])
      @socket_name = socket_name
    end

    def enabled?
      !@socket_name.to_s.empty?
    end

    def ready!
      notify!("READY=1\nSTATUS=text-stats MCP endpoint ready")
    end

    def stopping!
      return unless enabled?

      notify!("STOPPING=1\nSTATUS=text-stats MCP endpoint stopping")
    rescue ConfigurationError => error
      warn "text-stats MCP systemd notification failed during shutdown: #{error.message}"
    end

    private

    def notify!(message)
      return unless enabled?

      path = @socket_name.start_with?("@") ? "\0#{@socket_name.delete_prefix("@")} " : @socket_name
      path = path.delete_suffix(" ") if @socket_name.start_with?("@")
      socket = Socket.new(Socket::AF_UNIX, Socket::SOCK_DGRAM, 0)
      socket.connect(Socket.pack_sockaddr_un(path))
      socket.send(message, 0)
    rescue SystemCallError, SocketError => error
      raise ConfigurationError, "unable to notify systemd through NOTIFY_SOCKET: #{error.message}"
    ensure
      socket&.close
    end
  end

  class ShutdownCoordinator
    def initialize(notifier)
      @notifier = notifier
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

      Thread.new do
        @notifier.stopping!
        server.shutdown
      end
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
      when "/livez"
        return method_not_allowed("GET") unless request.get?

        json_response(200, status: "live")
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
      parsed.scheme&.casecmp?("http") && parsed.host&.casecmp?(@host) && parsed.port == @port &&
        parsed.userinfo.nil? && parsed.path.to_s.empty? && parsed.query.nil? && parsed.fragment.nil?
    rescue URI::InvalidURIError
      false
    end

    def unauthorized_response
      [401, { "content-type" => "application/json", "cache-control" => "no-store", "www-authenticate" => "Bearer" },
       [JSON.generate(error: "unauthorized")]]
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
      [status, { "content-type" => "application/json", "cache-control" => "no-store" }, [JSON.generate(payload)]]
    end
  end

  module_function

  def load_configuration
    bind = ENV.fetch("TEXT_STATS_MCP_HTTP_BIND", HTTP_BIND)
    raise ConfigurationError, "TEXT_STATS_MCP_HTTP_BIND must be 127.0.0.1" unless bind == HTTP_BIND

    port = Integer(ENV.fetch("TEXT_STATS_MCP_HTTP_PORT", HTTP_DEFAULT_PORT.to_s), 10)
    raise ConfigurationError, "TEXT_STATS_MCP_HTTP_PORT must be between 1 and 65535" unless (1..65_535).cover?(port)

    [bind, port, load_token]
  rescue ArgumentError
    raise ConfigurationError, "TEXT_STATS_MCP_HTTP_PORT must be a base-10 integer between 1 and 65535"
  end

  def load_token
    explicit = ENV["TEXT_STATS_MCP_HTTP_TOKEN_FILE"]
    credentials_directory = ENV["CREDENTIALS_DIRECTORY"]
    if explicit && credentials_directory
      raise ConfigurationError,
            "configure TEXT_STATS_MCP_HTTP_TOKEN_FILE or the systemd credential directory, not both"
    end

    if explicit
      path = File.expand_path(explicit, Dir.pwd)
      enforce_file_metadata = true
    elsif credentials_directory
      unless credentials_directory.start_with?(File::SEPARATOR)
        raise ConfigurationError, "CREDENTIALS_DIRECTORY must be an absolute path"
      end
      path = File.join(credentials_directory, SYSTEMD_CREDENTIAL_NAME)
      enforce_file_metadata = false
    else
      raise ConfigurationError, "a token file or systemd credential is required"
    end

    token = read_token_file(path, enforce_file_metadata: enforce_file_metadata)
    unless token.match?(/\A[!-~]{32,128}\z/)
      raise ConfigurationError, "token material must contain 32 to 128 non-whitespace printable ASCII characters"
    end
    token
  end

  def read_token_file(path, enforce_file_metadata:)
    flags = File::RDONLY | File::NOFOLLOW | File::NONBLOCK
    raw = File.open(path, flags) do |file|
      stat = file.stat
      raise ConfigurationError, "token file must be a regular non-symlink file: #{path}" unless stat.file?
      if enforce_file_metadata
        unless stat.uid == Process.euid
          raise ConfigurationError, "token file must be owned by the service user: #{path}"
        end
        unless (stat.mode & 0o077).zero?
          raise ConfigurationError, "token file must not be accessible by group or other users: #{path}"
        end
      end
      file.read(TOKEN_FILE_MAX_BYTES + 1).to_s
    end
    raise ConfigurationError, "token file exceeds #{TOKEN_FILE_MAX_BYTES} bytes: #{path}" if raw.bytesize > TOKEN_FILE_MAX_BYTES

    raw.sub(/\r?\n\z/, "")
  rescue Errno::ELOOP
    raise ConfigurationError, "token file must be a regular non-symlink file: #{path}"
  rescue ConfigurationError
    raise
  rescue SystemCallError => error
    raise ConfigurationError, "unable to read token file #{path}: #{error.message}"
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

  def run
    $stderr.sync = true
    transport = nil
    server = nil
    status = 0
    notifier = SystemdNotifier.new

    begin
      bind, port, token = load_configuration
      token_matcher = build_token_matcher(token)
      transport = MCP::Server::Transports::StreamableHTTPTransport.new(
        build_server,
        enable_json_response: true,
        session_idle_timeout: HTTP_SESSION_IDLE_TIMEOUT,
        max_sessions: HTTP_MAX_SESSIONS,
        dns_rebinding_protection: false,
        session_request_validator: ->(request, _session_id) { token_matcher.call(request) },
        max_request_bytes: HTTP_MAX_REQUEST_BYTES
      )
      application = HttpApplication.new(transport: transport, host: bind, port: port, token_matcher: token_matcher)
      shutdown = ShutdownCoordinator.new(notifier)
      %w[TERM INT].each { |signal| Signal.trap(signal) { shutdown.request } }

      warn "text-stats MCP systemd service starting on http://#{bind}:#{port}"
      server = BoundedHTTPServer.new(
        BindAddress: bind,
        Port: port,
        AccessLog: [],
        Logger: WEBrick::Log.new($stderr, WEBrick::Log::WARN),
        RequestBodyLimit: HTTP_MAX_REQUEST_BYTES,
        RequestCallback: ->(request, _response) { request.preload_bounded_body! }
      )
      server.mount "/", Rackup::Handler::WEBrick, application
      if shutdown.attach(server)
        warn "text-stats MCP systemd shutdown requested during startup"
      else
        notifier.ready!
        warn "text-stats MCP systemd service ready"
      end
      server.start
    rescue ConfigurationError => error
      warn "text-stats MCP systemd service configuration failed: #{error.message}"
      status = 78
    rescue SystemCallError => error
      warn "text-stats MCP systemd service failed: #{error.message}"
      status = 1
    ensure
      transport&.close
      warn "text-stats MCP systemd service stopped" if server
    end

    status
  end
end

exit TextStatsMcpSystemd.run if $PROGRAM_NAME == __FILE__
