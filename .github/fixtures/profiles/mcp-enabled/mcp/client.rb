#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "net/http"
require "open3"
require "optparse"
require "rbconfig"
require "timeout"
require "uri"

module TextStatsMcpClient
  PROTOCOL_VERSION = "2025-11-25"
  CONTRACT_VERSION = "1"
  DEFAULT_ENDPOINT = "http://127.0.0.1:4570/mcp"
  DEFAULT_TIMEOUT = 5.0
  MAX_TIMEOUT = 30.0
  DEFAULT_MAX_PAGES = 32
  MAX_PAGES = 128
  MAX_ARGUMENT_BYTES = 65_536
  ROOT = File.expand_path("..", __dir__)
  SERVER = File.join(ROOT, "mcp", "server.rb")

  class Failure < StandardError
    attr_reader :exit_code

    def initialize(message, exit_code)
      super(message)
      @exit_code = exit_code
    end
  end

  class UsageFailure < Failure
    def initialize(message)
      super("usage error: #{message}", 2)
    end
  end

  class TransportFailure < Failure
    def initialize(message = "transport failure")
      super(message, 3)
    end
  end

  class AuthenticationFailure < Failure
    def initialize(message = "authentication failure: Bearer token was rejected or unavailable")
      super(message, 4)
    end
  end

  class TimeoutFailure < Failure
    def initialize(message = "timeout: MCP operation exceeded the bounded timeout")
      super(message, 5)
    end
  end

  class JsonRpcFailure < Failure
    attr_reader :error

    def initialize(error)
      @error = error
      code = error.is_a?(Hash) ? error["code"] : nil
      label = code.nil? ? "unknown" : code
      super("JSON-RPC error: code #{label}", 6)
    end
  end

  class ProtocolFailure < Failure
    def initialize(message = "protocol failure: invalid MCP response")
      super(message, 6)
    end
  end

  class RequestPolicyFailure < Failure
    def initialize(status)
      super("HTTP request-policy failure: status #{status}", 10)
    end
  end

  class CapacityFailure < Failure
    def initialize(status)
      super("HTTP capacity failure: status #{status}", 11)
    end
  end

  class ToolResultFailure < Failure
    attr_reader :payload

    def initialize(payload)
      @payload = payload
      super("MCP tool result reported isError=true", 7)
    end
  end

  class InvalidResultFailure < Failure
    def initialize(message = "invalid MCP result")
      super(message, 8)
    end
  end

  class PaginationFailure < Failure
    def initialize(message)
      super("pagination failure: #{message}", 9)
    end
  end

  module Protocol
    module_function

    def request(id, method, params = nil)
      message = { "jsonrpc" => "2.0", "id" => id, "method" => method }
      message["params"] = params unless params.nil?
      message
    end

    def notification(method, params = nil)
      message = { "jsonrpc" => "2.0", "method" => method }
      message["params"] = params unless params.nil?
      message
    end

    def result(response, expected_id)
      unless response.is_a?(Hash) && response["jsonrpc"] == "2.0" && response["id"] == expected_id
        raise ProtocolFailure
      end

      raise JsonRpcFailure, response["error"] if response.key?("error")
      raise ProtocolFailure unless response.key?("result")

      response["result"]
    end

    def object_result(response, expected_id)
      value = result(response, expected_id)
      raise InvalidResultFailure unless value.is_a?(Hash)

      value
    end

    def initialize_result(response, expected_id)
      value = object_result(response, expected_id)
      server_info = value["serverInfo"]
      valid_server_info = server_info.is_a?(Hash) &&
                          server_info["name"].is_a?(String) &&
                          server_info["version"].is_a?(String)
      valid = value["protocolVersion"].is_a?(String) &&
              value["capabilities"].is_a?(Hash) &&
              valid_server_info
      raise InvalidResultFailure, "invalid MCP initialize result" unless valid

      value
    end

    def tools_list_result(response, expected_id)
      value = object_result(response, expected_id)
      tools = value["tools"]
      valid_tools = tools.is_a?(Array) && tools.all? do |tool|
        tool.is_a?(Hash) && tool["name"].is_a?(String) && !tool["name"].empty? &&
          tool["inputSchema"].is_a?(Hash)
      end
      valid_meta = !value.key?("_meta") || value["_meta"].is_a?(Hash)
      raise InvalidResultFailure, "invalid MCP tools/list result" unless valid_tools && valid_meta

      value
    end

    def tools_call_result(response, expected_id)
      value = object_result(response, expected_id)
      content = value["content"]
      valid_content = content.is_a?(Array) && content.all? { |block| valid_content_block?(block) }
      valid_is_error = !value.key?("isError") || [true, false].include?(value["isError"])
      valid_structured_content = !value.key?("structuredContent") || value["structuredContent"].is_a?(Hash)
      valid_meta = !value.key?("_meta") || value["_meta"].is_a?(Hash)
      unless valid_content && valid_is_error && valid_structured_content && valid_meta
        raise InvalidResultFailure, "invalid MCP tools/call result"
      end

      value
    end

    def valid_content_block?(block)
      return false unless block.is_a?(Hash)

      case block["type"]
      when "text"
        block["text"].is_a?(String)
      when "image", "audio"
        block["data"].is_a?(String) && block["mimeType"].is_a?(String)
      when "resource_link"
        block["name"].is_a?(String) && block["uri"].is_a?(String)
      when "resource"
        resource = block["resource"]
        return false unless resource.is_a?(Hash) && resource["uri"].is_a?(String)

        resource["text"].is_a?(String) ^ resource["blob"].is_a?(String)
      else
        false
      end
    end
  end

  RpcResponse = Struct.new(:id, :message, keyword_init: true)

  class StdioTransport
    def initialize(timeout_seconds)
      @timeout = timeout_seconds
      @next_id = 0
      @closed = false
      @stdin, @stdout, @stderr, @wait_thread = Open3.popen3(
        { "RUBYOPT" => nil },
        "bundle",
        "exec",
        RbConfig.ruby,
        SERVER,
        chdir: ROOT,
        pgroup: true
      )
      @stdin.sync = true
      @diagnostics_thread = Thread.new do
        @stderr.read
      rescue IOError, SystemCallError
        ""
      end
    rescue Errno::ENOENT, SystemCallError
      close_streams
      raise TransportFailure, "stdio transport failure: fixed bundled server could not start"
    end

    def request(method, params = {})
      id = next_id
      write(Protocol.request(id, method, params))
      RpcResponse.new(id: id, message: read_response(id))
    end

    def notify(method, params = {})
      write(Protocol.notification(method, params))
      nil
    end

    def close
      return if @closed

      @closed = true
      @stdin.close unless @stdin.closed?
      wait_for_exit
    ensure
      close_streams
      @diagnostics_thread&.join(0.2)
    end

    private

    def next_id
      @next_id += 1
    end

    def write(message)
      @stdin.write(JSON.generate(message))
      @stdin.write("\n")
      @stdin.flush
    rescue IOError, SystemCallError
      raise TransportFailure, "stdio transport failure: server input closed"
    end

    def read_response(expected_id)
      deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + @timeout

      loop do
        remaining = deadline - Process.clock_gettime(Process::CLOCK_MONOTONIC)
        raise TimeoutFailure, "timeout: stdio MCP response was not received" unless remaining.positive?

        line = Timeout.timeout(remaining) { @stdout.gets }
        raise TransportFailure, "stdio transport failure: server output closed" if line.nil?

        response = JSON.parse(line)
        unless response.is_a?(Hash) && response["jsonrpc"] == "2.0"
          raise ProtocolFailure
        end

        if !response.key?("id") && response.key?("method")
          next
        end

        raise ProtocolFailure unless response["id"] == expected_id

        return response
      end
    rescue Timeout::Error
      raise TimeoutFailure, "timeout: stdio MCP response was not received"
    rescue JSON::ParserError
      raise ProtocolFailure
    rescue IOError, SystemCallError
      raise TransportFailure, "stdio transport failure: server output could not be read"
    end

    def wait_for_exit
      return unless @wait_thread
      return if wait_with_timeout(@timeout)

      signal_process("TERM")
      return if wait_with_timeout(1.0)

      signal_process("KILL")
      wait_with_timeout(1.0)
    end

    def wait_with_timeout(seconds)
      Timeout.timeout(seconds) do
        @wait_thread.value
        true
      end
    rescue Timeout::Error
      false
    rescue Errno::ECHILD
      true
    end

    def signal_process(signal)
      return unless @wait_thread&.alive?

      Process.kill(signal, -@wait_thread.pid)
    rescue Errno::ESRCH
      nil
    end

    def close_streams
      [@stdin, @stdout, @stderr].each do |stream|
        stream.close unless stream.nil? || stream.closed?
      rescue IOError
        nil
      end
    end
  end

  class HttpTransport
    attr_reader :endpoint

    def initialize(endpoint, timeout_seconds)
      @endpoint = parse_endpoint(endpoint)
      @timeout = timeout_seconds
      @token = ENV["TEXT_STATS_MCP_HTTP_TOKEN"]
      raise AuthenticationFailure if @token.nil? || @token.empty?

      @session_id = nil
      @next_id = 0
      @http = Net::HTTP.new(@endpoint.host, @endpoint.port, nil)
      @http.open_timeout = @timeout
      @http.read_timeout = @timeout
      @http.write_timeout = @timeout if @http.respond_to?(:write_timeout=)
      check_readiness
    end

    def request(method, params = {})
      id = next_id
      response = post(Protocol.request(id, method, params), request_id: id)
      response
    end

    def notify(method, params = {})
      post(Protocol.notification(method, params), request_id: nil)
      nil
    end

    def close
      cleanup_error = nil
      begin
        delete_session if @session_id
      rescue Failure, IOError, SystemCallError, Timeout::Error => error
        cleanup_error = error
      ensure
        begin
          @http.finish if @http.started?
        rescue IOError, SystemCallError, Timeout::Error => error
          cleanup_error ||= TransportFailure.new("HTTP cleanup failure: connection could not be closed")
        end
      end
      raise cleanup_error if cleanup_error
    end

    private

    def parse_endpoint(value)
      uri = URI.parse(value || DEFAULT_ENDPOINT)
      valid = uri.is_a?(URI::HTTP) && uri.scheme == "http" && uri.host == "127.0.0.1" &&
              uri.userinfo.nil? && uri.path == "/mcp" && uri.query.nil? && uri.fragment.nil? &&
              uri.port.between?(1, 65_535)
      raise UsageFailure, "HTTP endpoint must be an http://127.0.0.1[:port]/mcp URL" unless valid

      uri
    rescue URI::InvalidURIError
      raise UsageFailure, "HTTP endpoint must be an http://127.0.0.1[:port]/mcp URL"
    end

    def next_id
      @next_id += 1
    end

    def check_readiness
      request = Net::HTTP::Get.new("/readyz")
      set_common_headers(request)
      response = perform(request)
      return if response.code == "200"

      classify_http_failure(response)
    end

    def post(payload, request_id:)
      path = @endpoint.request_uri
      request = Net::HTTP::Post.new(path)
      set_common_headers(request)
      request["Accept"] = "application/json, text/event-stream"
      request["Content-Type"] = "application/json"
      request["Authorization"] = "Bearer #{@token}"
      request["Mcp-Session-Id"] = @session_id if @session_id
      request["MCP-Protocol-Version"] = PROTOCOL_VERSION if @session_id
      request.body = JSON.generate(payload)

      response = perform(request)
      classify_http_failure(response) unless response.code.start_with?("2")
      return response if request_id.nil?

      parsed = JSON.parse(response.body)
      raise ProtocolFailure unless parsed.is_a?(Hash)

      if payload["method"] == "initialize"
        @session_id = response["mcp-session-id"]
        raise ProtocolFailure unless @session_id && !@session_id.empty?
      end
      RpcResponse.new(id: request_id, message: parsed)
    rescue JSON::ParserError
      raise ProtocolFailure
    end

    def delete_session
      request = Net::HTTP::Delete.new(@endpoint.request_uri)
      set_common_headers(request)
      request["Authorization"] = "Bearer #{@token}"
      request["Mcp-Session-Id"] = @session_id
      request["MCP-Protocol-Version"] = PROTOCOL_VERSION
      response = perform(request)
      classify_http_failure(response) unless response.code.start_with?("2")
    end

    def set_common_headers(request)
      request["Host"] = authority
    end

    def authority
      @endpoint.port == 80 ? @endpoint.host : "#{@endpoint.host}:#{@endpoint.port}"
    end

    def perform(request)
      Timeout.timeout(@timeout) do
        @http.start unless @http.started?
        @http.request(request)
      end
    rescue Timeout::Error
      raise TimeoutFailure, "timeout: HTTP MCP operation exceeded the bounded timeout"
    rescue IOError, SystemCallError
      raise TransportFailure, "HTTP transport failure: endpoint was unavailable"
    end

    def classify_http_failure(response)
      case response.code.to_i
      when 401
        raise AuthenticationFailure
      when 403, 413
        raise RequestPolicyFailure, response.code
      when 503
        raise CapacityFailure, response.code
      else
        raise ProtocolFailure, "HTTP protocol failure: status #{response.code}"
      end
    end
  end

  class Client
    def initialize(transport, max_pages: DEFAULT_MAX_PAGES)
      @transport = transport
      @max_pages = max_pages
    end

    def execute(command)
      initialization = initialize_session
      case command.fetch(:name)
      when :server_info
        envelope("server-info", initialization)
      when :tools_list
        tools_list
      when :tools_show
        tools_show(command.fetch(:tool))
      when :tools_call
        tools_call(command.fetch(:tool), command.fetch(:arguments))
      when :tools_run
        tools_run(command.fetch(:calls))
      else
        raise UsageFailure, "unknown command"
      end
    end

    private

    def initialize_session
      response = @transport.request(
        "initialize",
        {
          "protocolVersion" => PROTOCOL_VERSION,
          "capabilities" => {},
          "clientInfo" => { "name" => "text_stats_bundled_client", "version" => "1.0.0" }
        }
      )
      result = Protocol.initialize_result(response.message, response.id)
      unless result["protocolVersion"] == PROTOCOL_VERSION
        raise ProtocolFailure, "protocol failure: server selected an unsupported revision"
      end

      @transport.notify("notifications/initialized", {})
      result
    rescue KeyError
      raise ProtocolFailure
    end

    def tools_list
      pages = []
      requested_cursors = {}
      cursor = nil

      @max_pages.times do
        raise PaginationFailure, "cursor repeated before request" if !cursor.nil? && requested_cursors[cursor]

        requested_cursors[cursor] = true unless cursor.nil?
        params = cursor.nil? ? {} : { "cursor" => cursor }
        response = @transport.request("tools/list", params)
        result = Protocol.tools_list_result(response.message, response.id)
        pages << { "requestCursor" => cursor, "mcpResult" => result }

        break unless result.key?("nextCursor")

        next_cursor = result["nextCursor"]
        raise PaginationFailure, "nextCursor must be a string" unless next_cursor.is_a?(String)
        raise PaginationFailure, "cursor repeated before pagination completed" if requested_cursors[next_cursor]

        cursor = next_cursor
      end

      if pages.length == @max_pages && pages.last.fetch("mcpResult").key?("nextCursor")
        raise PaginationFailure, "page limit #{@max_pages} reached"
      end

      {
        "contractVersion" => CONTRACT_VERSION,
        "operation" => "tools/list",
        "pages" => pages,
        "metadata" => { "pageCount" => pages.length }
      }
    rescue KeyError
      raise ProtocolFailure
    end

    def tools_show(tool_name)
      raise UsageFailure, "tool name must be non-empty" if tool_name.to_s.empty?

      inventory = tools_list
      tool = inventory.fetch("pages").flat_map { |page| page.fetch("mcpResult").fetch("tools") }
                   .find { |candidate| candidate.is_a?(Hash) && candidate["name"] == tool_name }
      raise UsageFailure, "tool #{tool_name.inspect} was not found in tools/list" unless tool

      {
        "contractVersion" => CONTRACT_VERSION,
        "operation" => "tools/show",
        "tool" => tool,
        "metadata" => { "source" => "derived from tools/list", "pageCount" => inventory.fetch("metadata").fetch("pageCount") }
      }
    rescue KeyError, TypeError
      raise ProtocolFailure, "protocol failure: tools/list result has no usable tool inventory"
    end

    def tools_call(tool_name, arguments)
      raise UsageFailure, "tool name must be non-empty" if tool_name.to_s.empty?

      response = @transport.request(
        "tools/call",
        { "name" => tool_name, "arguments" => arguments }
      )
      result = Protocol.tools_call_result(response.message, response.id)
      payload = envelope("tools/call", result)
      raise ToolResultFailure, payload if result["isError"] == true

      payload
    rescue KeyError
      raise ProtocolFailure
    end

    def tools_run(calls)
      raise UsageFailure, "tools run requires at least one call" if calls.empty?

      results = []
      calls.each_with_index do |call, index|
        response = @transport.request(
          "tools/call",
          { "name" => call.fetch(:tool), "arguments" => call.fetch(:arguments) }
        )
        result = Protocol.tools_call_result(response.message, response.id)
        results << { "index" => index, "tool" => call.fetch(:tool), "mcpResult" => result }
        if result["isError"] == true
          raise ToolResultFailure, {
            "contractVersion" => CONTRACT_VERSION,
            "operation" => "tools/run",
            "results" => results
          }
        end
      end

      {
        "contractVersion" => CONTRACT_VERSION,
        "operation" => "tools/run",
        "results" => results
      }
    rescue KeyError
      raise ProtocolFailure
    end

    def envelope(operation, result)
      { "contractVersion" => CONTRACT_VERSION, "operation" => operation, "mcpResult" => result }
    end
  end

  module_function

  def parse_timeout(value)
    timeout = Float(value)
    raise UsageFailure, "timeout must be greater than zero and at most #{MAX_TIMEOUT}" unless timeout.positive? && timeout <= MAX_TIMEOUT

    timeout
  rescue ArgumentError, TypeError
    raise UsageFailure, "timeout must be a number between 0 and #{MAX_TIMEOUT}"
  end

  def parse_max_pages(value)
    pages = Integer(value, 10)
    raise UsageFailure, "max-pages must be between 1 and #{MAX_PAGES}" unless (1..MAX_PAGES).cover?(pages)

    pages
  rescue ArgumentError, TypeError
    raise UsageFailure, "max-pages must be a base-10 integer between 1 and #{MAX_PAGES}"
  end

  def parse_json_arguments(value)
    raise UsageFailure, "arguments exceed #{MAX_ARGUMENT_BYTES} bytes" if value.bytesize > MAX_ARGUMENT_BYTES

    parsed = JSON.parse(value)
    raise UsageFailure, "arguments must be a JSON object" unless parsed.is_a?(Hash)

    parsed
  rescue JSON::ParserError
    raise UsageFailure, "arguments must be valid JSON"
  end

  def read_arguments(options)
    sources = options.values_at(:arguments, :arguments_stdin).compact
    raise UsageFailure, "exactly one arguments source is required" unless sources.length == 1

    source = if options[:arguments]
               options[:arguments]
             else
               input = STDIN.read(MAX_ARGUMENT_BYTES + 1)
               raise UsageFailure, "stdin arguments exceed #{MAX_ARGUMENT_BYTES} bytes" if input.bytesize > MAX_ARGUMENT_BYTES

               input
             end
    parse_json_arguments(source)
  end

  def parse_global_options(argv)
    options = { transport: "stdio", endpoint: DEFAULT_ENDPOINT, timeout: DEFAULT_TIMEOUT, max_pages: DEFAULT_MAX_PAGES }
    parser = OptionParser.new do |opts|
      opts.on("--transport TRANSPORT", %w[stdio http], "MCP transport") { |value| options[:transport] = value }
      opts.on("--endpoint URL", "loopback Streamable HTTP endpoint") { |value| options[:endpoint] = value }
      opts.on("--url URL", "alias for --endpoint") { |value| options[:endpoint] = value }
      opts.on("--timeout SECONDS", "bounded operation timeout") { |value| options[:timeout] = parse_timeout(value) }
      opts.on("--max-pages COUNT", "bounded tools/list page count") { |value| options[:max_pages] = parse_max_pages(value) }
      opts.on("--help", "show help") { puts opts; exit 0 }
    end
    parser.parse!(argv)
    options
  rescue OptionParser::ParseError => error
    raise UsageFailure, error.message
  end

  def parse_command(argv)
    command = argv.shift
    case command
    when "server-info"
      raise UsageFailure, "server-info accepts no arguments" unless argv.empty?

      { name: :server_info }
    when "tools"
      parse_tools_command(argv)
    else
      raise UsageFailure, "command must be server-info or tools"
    end
  end

  def parse_tools_command(argv)
    operation = argv.shift
    case operation
    when "list"
      raise UsageFailure, "tools list accepts no arguments" unless argv.empty?

      { name: :tools_list }
    when "show"
      tool = argv.shift
      raise UsageFailure, "tools show requires exactly one tool name" if tool.nil? || argv.any?

      { name: :tools_show, tool: tool }
    when "call"
      tool = argv.shift
      raise UsageFailure, "tools call requires a tool name" if tool.nil?

      options = parse_argument_options(argv)
      { name: :tools_call, tool: tool, arguments: read_arguments(options) }
    when "run"
      { name: :tools_run, calls: parse_run_calls(argv) }
    else
      raise UsageFailure, "tools command must be list, show, call, or run"
    end
  end

  def parse_argument_options(argv)
    options = { arguments: nil, arguments_stdin: nil }
    parser = OptionParser.new do |opts|
      opts.on("--arguments JSON", "JSON object arguments") { |value| options[:arguments] = value }
      opts.on("--arguments-stdin", "read JSON object arguments from stdin") { options[:arguments_stdin] = true }
    end
    parser.parse!(argv)
    options
  rescue OptionParser::ParseError => error
    raise UsageFailure, error.message
  end

  def parse_run_calls(argv)
    calls = []
    current = nil
    parser = OptionParser.new do |opts|
      opts.on("--call TOOL", "append one sequential tools/call operation") do |tool|
        raise UsageFailure, "each --call needs --arguments" if current && !current.key?(:arguments)

        current = { tool: tool }
        calls << current
      end
      opts.on("--arguments JSON", "arguments for the most recent --call") do |value|
        raise UsageFailure, "--arguments must follow --call" unless current
        raise UsageFailure, "each --call accepts one arguments value" if current.key?(:arguments)

        current[:arguments] = parse_json_arguments(value)
      end
    end
    parser.parse!(argv)
    raise UsageFailure, "each --call needs --arguments" if current && !current.key?(:arguments)
    calls
  rescue OptionParser::ParseError => error
    raise UsageFailure, error.message
  end

  def emit(payload, pretty: false)
    text = pretty ? JSON.pretty_generate(payload) : JSON.generate(payload)
    $stdout.write(text)
    $stdout.write("\n")
    $stdout.flush
  end

  def run(argv)
    transport = nil
    exit_code = nil

    begin
      command_name_index = argv.index { |argument| %w[server-info tools].include?(argument) }
      raise UsageFailure, "a command is required" unless command_name_index

      global_arguments = argv.slice!(0, command_name_index)
      options = parse_global_options(global_arguments)
      raise UsageFailure, "unknown global option #{global_arguments.first.inspect}" unless global_arguments.empty?
      command = parse_command(argv)
      transport = if options[:transport] == "stdio"
                    StdioTransport.new(options[:timeout])
                  else
                    HttpTransport.new(options[:endpoint], options[:timeout])
                  end
      result = Client.new(transport, max_pages: options[:max_pages]).execute(command)
      emit(result)
      exit_code = 0
    rescue ToolResultFailure => error
      emit(error.payload)
      warn error.message
      exit_code = error.exit_code
    rescue Failure => error
      warn error.message
      exit_code = error.exit_code
    rescue StandardError
      warn "client failure: operation did not complete"
      exit_code = 3
    ensure
      begin
        transport&.close
      rescue Failure => error
        warn "HTTP cleanup failure: #{error.message}"
        exit_code = error.exit_code if exit_code == 0
      rescue StandardError
        warn "HTTP cleanup failure: session could not be released"
        exit_code = 3 if exit_code == 0
      end
    end

    exit_code
  end
end

if $PROGRAM_NAME == __FILE__
  begin
    exit TextStatsMcpClient.run(ARGV)
  rescue TextStatsMcpClient::Failure => error
    warn error.message
    exit error.exit_code
  end
end
