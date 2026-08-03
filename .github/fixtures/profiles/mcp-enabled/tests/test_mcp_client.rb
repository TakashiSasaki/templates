# frozen_string_literal: true

require "json"
require "minitest/autorun"
require "net/http"
require "open3"
require "rbconfig"
require "socket"
require "uri"
require "stringio"
require "timeout"
require_relative "../mcp/client"

class TextStatsMcpClientTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  CLIENT = File.join(ROOT, "mcp/client.rb")
  HTTP_SERVER = File.join(ROOT, "mcp/http_server.rb")
  HOST = "127.0.0.1"
  TOKEN = "fixture-http-token-0123456789abcdef"
  BUNDLE_RUBY = ["bundle", "exec", RbConfig.ruby].freeze

  class HttpServerProcess
    attr_reader :port

    def self.free_port
      listener = TCPServer.new(HOST, 0)
      listener.addr.fetch(1)
    ensure
      listener&.close
    end

    def initialize(extra_environment: {})
      @port = self.class.free_port
      environment = {
        "TEXT_STATS_MCP_HTTP_BIND" => HOST,
        "TEXT_STATS_MCP_HTTP_PORT" => port.to_s,
        "TEXT_STATS_MCP_HTTP_TOKEN" => TOKEN
      }.merge(extra_environment)
      @stdin, @stdout, @stderr, @wait_thread = Open3.popen3(
        environment,
        *BUNDLE_RUBY,
        HTTP_SERVER,
        chdir: ROOT
      )
      @stdin.close
      wait_until_ready
    end

    def stop
      return unless @wait_thread

      Process.kill("TERM", @wait_thread.pid) if @wait_thread.alive?
      Timeout.timeout(3) { @wait_thread.value }
    rescue Errno::ESRCH, Timeout::Error
      Process.kill("KILL", @wait_thread.pid) if @wait_thread&.alive?
      @wait_thread&.value
    ensure
      [@stdout, @stderr].each do |stream|
        stream.close unless stream.closed?
      rescue IOError
        nil
      end
      @wait_thread = nil
    end

    private

    def wait_until_ready
      deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + 5
      loop do
        raise "HTTP server exited before readiness" unless @wait_thread.alive?

        begin
          http = Net::HTTP.new(HOST, port, nil)
          http.open_timeout = 1
          http.read_timeout = 1
          request = Net::HTTP::Get.new("/readyz")
          return if http.start { |connection| connection.request(request).code == "200" }
        rescue IOError, SystemCallError, Timeout::Error
          nil
        end

        raise "HTTP server readiness timed out" if Process.clock_gettime(Process::CLOCK_MONOTONIC) >= deadline

        sleep 0.05
      end
    end
  end

  class FakeTransport
    attr_reader :requests

    def initialize
      @next_id = 0
      @requests = []
    end

    def request(method, params = {})
      @next_id += 1
      @requests << [method, params]
      result = case method
               when "initialize"
                 {
                   "protocolVersion" => TextStatsMcpClient::PROTOCOL_VERSION,
                   "capabilities" => { "tools" => {} },
                   "serverInfo" => { "name" => "fake", "version" => "1" },
                   "futureInitializeField" => { "kept" => true }
                 }
               when "tools/list"
                 if params.key?("cursor")
                   {
                     "tools" => [],
                     "futurePageField" => "second",
                     "_meta" => { "page" => 2 }
                   }
                 else
                   {
                     "tools" => [{
                       "name" => "text_stats",
                       "inputSchema" => {
                         "type" => "object",
                         "properties" => { "text" => { "type" => "string" } },
                         "required" => ["text"],
                         "additionalProperties" => false
                       },
                       "futureToolField" => [1, 2, 3]
                     }],
                     "nextCursor" => "opaque-cursor",
                     "ttlMs" => 30_000,
                     "cacheScope" => "per-test",
                     "_meta" => { "page" => 1 },
                     "futurePageField" => "first"
                   }
                 end
               else
                 raise "unexpected fake request #{method.inspect}"
               end
      TextStatsMcpClient::RpcResponse.new(
        id: @next_id,
        message: { "jsonrpc" => "2.0", "id" => @next_id, "result" => result }
      )
    end

    def notify(method, params = {})
      @requests << [method, params]
    end
  end

  class RepeatedCursorTransport
    attr_reader :requests

    def initialize
      @next_id = 0
      @requests = []
      @cursor_a_requests = 0
    end

    def request(method, params = {})
      @next_id += 1
      @requests << [method, params]
      result = case method
               when "initialize"
                 {
                   "protocolVersion" => TextStatsMcpClient::PROTOCOL_VERSION,
                   "capabilities" => { "tools" => {} },
                   "serverInfo" => { "name" => "fake", "version" => "1" }
                 }
               when "tools/list"
                 if params.fetch("cursor", nil) == "a"
                   @cursor_a_requests += 1
                   @cursor_a_requests == 1 ? { "tools" => [], "nextCursor" => "a" } : { "tools" => [] }
                 else
                   { "tools" => [], "nextCursor" => "a" }
                 end
               else
                 raise "unexpected fake request #{method.inspect}"
               end
      TextStatsMcpClient::RpcResponse.new(
        id: @next_id,
        message: { "jsonrpc" => "2.0", "id" => @next_id, "result" => result }
      )
    end

    def notify(method, params = {})
      @requests << [method, params]
    end
  end

  class MalformedResultTransport
    attr_reader :requests

    def initialize(operation, result = {})
      @operation = operation
      @result = result
      @next_id = 0
      @requests = []
    end

    def request(method, params = {})
      @next_id += 1
      @requests << [method, params]
      result = case method
               when @operation
                 @result
               when "initialize"
                 {
                   "protocolVersion" => TextStatsMcpClient::PROTOCOL_VERSION,
                   "capabilities" => { "tools" => {} },
                   "serverInfo" => { "name" => "fake", "version" => "1" }
                 }
               else
                 raise "unexpected fake request #{method.inspect}"
               end
      TextStatsMcpClient::RpcResponse.new(
        id: @next_id,
        message: { "jsonrpc" => "2.0", "id" => @next_id, "result" => result }
      )
    end

    def notify(method, params = {})
      @requests << [method, params]
    end
  end

  class StreamingResponse
    attr_accessor :body
    attr_reader :code, :chunks_read

    def initialize(chunks, code: "200", headers: {})
      @chunks = chunks
      @code = code
      @headers = headers.transform_keys(&:downcase)
      @chunks_read = 0
    end

    def [](name)
      @headers[name.downcase]
    end

    def read_body
      @chunks.each do |chunk|
        @chunks_read += 1
        yield chunk
      end
    end
  end

  class StreamingHttp
    def initialize(response)
      @response = response
    end

    def started?
      true
    end

    def request(_request)
      yield @response
      @response
    end
  end

  def stdio_transport_for(*messages)
    transport = TextStatsMcpClient::StdioTransport.allocate
    transport.instance_variable_set(:@timeout, 0.1)
    transport.instance_variable_set(:@stdout, StringIO.new(messages.map { |message| JSON.generate(message) }.join("\n") + "\n"))
    transport
  end

  def run_client(*arguments, env: {})
    Open3.capture3(
      env,
      *BUNDLE_RUBY,
      CLIENT,
      *arguments,
      chdir: ROOT
    )
  end

  def parse_response(stdout)
    JSON.parse(stdout)
  rescue JSON::ParserError => error
    flunk "client did not emit one JSON response: #{error.message}; stdout=#{stdout.inspect}"
  end

  def test_stdio_server_info_is_lossless_and_keeps_diagnostics_off_stdout
    stdout, stderr, status = run_client("server-info")

    assert status.success?, stderr
    response = parse_response(stdout)
    assert_equal "1", response.fetch("contractVersion")
    assert_equal "2025-11-25", response.fetch("mcpResult").fetch("protocolVersion")
    assert_equal "text_stats_fixture", response.fetch("mcpResult").fetch("serverInfo").fetch("name")
    refute_includes stdout, "text-stats MCP stdio server starting"
    assert_equal "", stderr
  end

  def test_stdio_tools_list_and_local_tools_show_preserve_pages
    list_stdout, list_stderr, list_status = run_client("tools", "list")
    assert list_status.success?, list_stderr
    list_response = parse_response(list_stdout)
    page = list_response.fetch("pages").fetch(0)
    assert_nil page.fetch("requestCursor")
    assert_equal ["text_stats"], page.fetch("mcpResult").fetch("tools").map { |tool| tool.fetch("name") }
    refute page.fetch("mcpResult").key?("nextCursor")

    show_stdout, show_stderr, show_status = run_client("tools", "show", "text_stats")
    assert show_status.success?, show_stderr
    show_response = parse_response(show_stdout)
    assert_equal "tools/show", show_response.fetch("operation")
    assert_equal "text_stats", show_response.fetch("tool").fetch("name")
  end

  def test_tools_run_without_calls_fails_before_transport_creation
    transport_created = false
    status = nil

    stdout, stderr = capture_io do
      TextStatsMcpClient::StdioTransport.stub(
        :new,
        lambda do |_timeout|
          transport_created = true
          raise "unexpected transport creation"
        end
      ) do
        status = TextStatsMcpClient.run(["tools", "run"])
      end
    end

    assert_equal 2, status
    refute transport_created
    assert_equal "", stdout
    assert_includes stderr, "usage error: tools run requires at least one call"
  end

  def test_stdio_call_and_sequential_run_use_real_protocol_calls
    call_stdout, call_stderr, call_status = run_client(
      "tools",
      "call",
      "text_stats",
      "--arguments",
      JSON.generate("text" => "one two\n")
    )
    assert call_status.success?, call_stderr
    result = parse_response(call_stdout).fetch("mcpResult")
    assert_equal false, result.fetch("isError")
    assert_equal({ "bytes" => 8, "lines" => 1, "words" => 2 }, result.fetch("structuredContent"))

    run_stdout, run_stderr, run_status = run_client(
      "tools",
      "run",
      "--call",
      "text_stats",
      "--arguments",
      JSON.generate("text" => "alpha"),
      "--call",
      "text_stats",
      "--arguments",
      JSON.generate("text" => "beta gamma\n")
    )
    assert run_status.success?, run_stderr
    results = parse_response(run_stdout).fetch("results")
    assert_equal 2, results.length
    assert_equal({ "bytes" => 5, "lines" => 1, "words" => 1 }, results.fetch(0).fetch("mcpResult").fetch("structuredContent"))
    assert_equal({ "bytes" => 11, "lines" => 1, "words" => 2 }, results.fetch(1).fetch("mcpResult").fetch("structuredContent"))
  end

  def test_client_codec_preserves_unknown_fields_and_opaque_pages
    transport = FakeTransport.new
    result = TextStatsMcpClient::Client.new(transport).execute(name: :tools_list)

    assert_equal 2, result.fetch("pages").length
    assert_equal "opaque-cursor", result.fetch("pages").fetch(0).fetch("mcpResult").fetch("nextCursor")
    assert_equal 30_000, result.fetch("pages").fetch(0).fetch("mcpResult").fetch("ttlMs")
    assert_equal({ "page" => 1 }, result.fetch("pages").fetch(0).fetch("mcpResult").fetch("_meta"))
    assert_equal "first", result.fetch("pages").fetch(0).fetch("mcpResult").fetch("futurePageField")
    assert_equal "second", result.fetch("pages").fetch(1).fetch("mcpResult").fetch("futurePageField")
    assert_includes transport.requests.map(&:first), "notifications/initialized"
    refute_includes transport.requests.map(&:first), "tools/show"
  end

  def test_repeated_pagination_cursor_is_rejected_before_reuse
    transport = RepeatedCursorTransport.new

    error = assert_raises(TextStatsMcpClient::PaginationFailure) do
      TextStatsMcpClient::Client.new(transport).execute(name: :tools_list)
    end

    assert_equal 9, error.exit_code
    assert_equal 2, transport.requests.count { |method, _params| method == "tools/list" }
  end

  def test_malformed_operation_results_are_invalid_result_failures
    {
      tools_list: "tools/list",
      tools_call: "tools/call"
    }.each do |command, operation|
      transport = MalformedResultTransport.new(operation)
      error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
        command_args = command == :tools_call ? { name: command, tool: "text_stats", arguments: {} } : { name: command }
        TextStatsMcpClient::Client.new(transport).execute(**command_args)
      end

      assert_equal 8, error.exit_code
    end
  end

  def test_tools_call_rejects_non_object_result_metadata
    transport = MalformedResultTransport.new(
      "tools/call",
      "content" => [],
      "_meta" => "invalid"
    )

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      TextStatsMcpClient::Client.new(transport).execute(
        name: :tools_call,
        tool: "text_stats",
        arguments: {}
      )
    end

    assert_equal 8, error.exit_code
  end

  def test_tools_list_rejects_tool_definitions_without_required_input_schema
    transport = MalformedResultTransport.new(
      "tools/list",
      "tools" => [{ "name" => "text_stats" }]
    )

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      TextStatsMcpClient::Client.new(transport).execute(name: :tools_list)
    end

    assert_equal 8, error.exit_code
  end

  def test_tools_list_rejects_non_object_tool_metadata
    transport = MalformedResultTransport.new(
      "tools/list",
      "tools" => [{
        "name" => "text_stats",
        "inputSchema" => { "type" => "object" },
        "_meta" => "invalid"
      }]
    )

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      TextStatsMcpClient::Client.new(transport).execute(name: :tools_list)
    end

    assert_equal 8, error.exit_code
  end

  def test_tools_list_rejects_input_schema_without_object_discriminator
    transport = MalformedResultTransport.new(
      "tools/list",
      "tools" => [{ "name" => "text_stats", "inputSchema" => {} }]
    )

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      TextStatsMcpClient::Client.new(transport).execute(name: :tools_list)
    end

    assert_equal 8, error.exit_code
  end

  def test_tools_call_rejects_non_object_content_block_metadata
    transport = MalformedResultTransport.new(
      "tools/call",
      "content" => [{ "type" => "text", "text" => "ok", "_meta" => "invalid" }]
    )

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      TextStatsMcpClient::Client.new(transport).execute(
        name: :tools_call,
        tool: "text_stats",
        arguments: {}
      )
    end

    assert_equal 8, error.exit_code
  end

  def test_tools_call_rejects_non_object_embedded_resource_metadata
    transport = MalformedResultTransport.new(
      "tools/call",
      "content" => [{
        "type" => "resource",
        "resource" => {
          "uri" => "file:///x",
          "text" => "ok",
          "_meta" => "invalid"
        }
      }]
    )

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      TextStatsMcpClient::Client.new(transport).execute(
        name: :tools_call,
        tool: "text_stats",
        arguments: {}
      )
    end

    assert_equal 8, error.exit_code
  end


  def test_tools_list_rejects_non_object_result_metadata
    transport = MalformedResultTransport.new(
      "tools/list",
      "tools" => [],
      "_meta" => "invalid"
    )

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      TextStatsMcpClient::Client.new(transport).execute(name: :tools_list)
    end

    assert_equal 8, error.exit_code
  end

  def test_initialize_requires_protocol_capabilities_and_server_info_fields
    transport = MalformedResultTransport.new(
      "initialize",
      "protocolVersion" => TextStatsMcpClient::PROTOCOL_VERSION
    )

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      TextStatsMcpClient::Client.new(transport).execute(name: :server_info)
    end

    assert_equal 8, error.exit_code
    refute_includes transport.requests.map(&:first), "notifications/initialized"
  end

  def test_initialize_rejects_malformed_known_capability_shapes
    [
      { "tools" => "invalid" },
      { "tools" => { "listChanged" => "invalid" } }
    ].each do |capabilities|
      transport = MalformedResultTransport.new(
        "initialize",
        "protocolVersion" => TextStatsMcpClient::PROTOCOL_VERSION,
        "capabilities" => capabilities,
        "serverInfo" => { "name" => "fake", "version" => "1" }
      )

      error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
        TextStatsMcpClient::Client.new(transport).execute(name: :server_info)
      end

      assert_equal 8, error.exit_code
      refute_includes transport.requests.map(&:first), "notifications/initialized"
    end
  end

  def test_initialize_rejects_non_object_result_metadata
    transport = MalformedResultTransport.new(
      "initialize",
      "protocolVersion" => TextStatsMcpClient::PROTOCOL_VERSION,
      "capabilities" => { "tools" => {} },
      "serverInfo" => { "name" => "fake", "version" => "1" },
      "_meta" => "invalid"
    )

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      TextStatsMcpClient::Client.new(transport).execute(name: :server_info)
    end

    assert_equal 8, error.exit_code
    refute_includes transport.requests.map(&:first), "notifications/initialized"
  end

  def test_http_initialize_parse_failure_preserves_session_for_cleanup
    response_class = Struct.new(:code, :body, :headers) do
      def [](name)
        headers[name.downcase]
      end
    end
    response = response_class.new(
      "200",
      "{malformed",
      {
        "mcp-session-id" => "session-123",
        "content-type" => "application/json"
      }
    )

    transport = TextStatsMcpClient::HttpTransport.allocate
    transport.instance_variable_set(:@endpoint, URI.parse("http://127.0.0.1:4570/mcp"))
    transport.instance_variable_set(:@timeout, 0.1)
    transport.instance_variable_set(:@token, TOKEN)
    transport.instance_variable_set(:@session_id, nil)
    http = Object.new
    http.define_singleton_method(:started?) { false }
    transport.instance_variable_set(:@http, http)

    deleted_session = nil
    transport.define_singleton_method(:perform) { |_request, **_options| response }
    transport.define_singleton_method(:delete_session) { deleted_session = @session_id }

    error = assert_raises(TextStatsMcpClient::ProtocolFailure) do
      transport.send(
        :post,
        TextStatsMcpClient::Protocol.request(1, "initialize", {}),
        request_id: 1
      )
    end

    assert_equal 6, error.exit_code
    assert_equal "session-123", transport.instance_variable_get(:@session_id)
    transport.close
    assert_equal "session-123", deleted_session
  end

  def test_http_json_requests_reject_non_json_media_type
    response_class = Struct.new(:code, :body, :headers) do
      def [](name)
        headers[name.downcase]
      end
    end

    [
      ["initialize", { "mcp-session-id" => "session-json" }],
      ["tools/list", { "mcp-session-id" => "session-json" }]
    ].each do |method, headers|
      response = response_class.new(
        "200",
        JSON.generate("jsonrpc" => "2.0", "id" => 1, "result" => {}),
        headers.merge("content-type" => "text/plain; charset=utf-8")
      )
      transport = TextStatsMcpClient::HttpTransport.allocate
      transport.instance_variable_set(:@endpoint, URI.parse("http://127.0.0.1:4570/mcp"))
      transport.instance_variable_set(:@timeout, 0.1)
      transport.instance_variable_set(:@token, TOKEN)
      transport.instance_variable_set(:@session_id, "session-json")
      transport.define_singleton_method(:perform) { |_request, **_options| response }

      error = assert_raises(TextStatsMcpClient::ProtocolFailure) do
        transport.send(
          :post,
          TextStatsMcpClient::Protocol.request(1, method, {}),
          request_id: 1
        )
      end

      assert_equal 6, error.exit_code
    end
  end

  def test_http_notifications_require_202_response
    response_class = Struct.new(:code, :body, :headers) do
      def [](name)
        headers[name.downcase]
      end
    end
    response = response_class.new(
      "200",
      JSON.generate("jsonrpc" => "2.0", "error" => { "code" => -32_600 }),
      {}
    )

    transport = TextStatsMcpClient::HttpTransport.allocate
    transport.instance_variable_set(:@endpoint, URI.parse("http://127.0.0.1:4570/mcp"))
    transport.instance_variable_set(:@timeout, 0.1)
    transport.instance_variable_set(:@token, TOKEN)
    transport.instance_variable_set(:@session_id, "session-123")
    transport.define_singleton_method(:perform) { |_request| response }

    error = assert_raises(TextStatsMcpClient::ProtocolFailure) do
      transport.notify("notifications/initialized", {})
    end

    assert_equal 6, error.exit_code
    response = response_class.new("202", "", {})
    assert_nil transport.notify("notifications/initialized", {})
  end

  def test_tools_call_rejects_content_blocks_without_type_specific_fields
    invalid_blocks = [
      { "type" => "text" },
      { "type" => "image", "mimeType" => "image/png" },
      { "type" => "audio", "data" => "encoded" },
      { "type" => "resource", "resource" => { "uri" => "file:///tmp/item" } },
      { "type" => "resource_link", "uri" => "file:///tmp/item" },
      { "type" => "unknown" }
    ]

    invalid_blocks.each do |block|
      transport = MalformedResultTransport.new("tools/call", "content" => [block])
      error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
        TextStatsMcpClient::Client.new(transport).execute(
          name: :tools_call,
          tool: "text_stats",
          arguments: {}
        )
      end

      assert_equal 8, error.exit_code
    end
  end

  def test_response_file_argument_mode_is_rejected
    stdout, stderr, status = run_client(
      "tools",
      "call",
      "text_stats",
      "--arguments-file",
      "/tmp/mcp-client-arguments.json"
    )

    assert_equal "", stdout
    assert_equal 2, status.exitstatus
    assert_includes stderr, "invalid option: --arguments-file"
  end

  def test_stdio_response_body_limit_is_enforced_before_json_parse
    oversized_text = "x" * TextStatsMcpClient::MAX_RESPONSE_BYTES
    transport = stdio_transport_for(
      "jsonrpc" => "2.0",
      "id" => 1,
      "result" => { "content" => [{ "type" => "text", "text" => oversized_text }] }
    )

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      transport.send(:read_response, 1)
    end

    assert_equal 8, error.exit_code
  end

  def test_http_initialize_response_body_limit_preserves_session_for_cleanup
    response = StreamingResponse.new(
      [
        "x" * TextStatsMcpClient::MAX_RESPONSE_BYTES,
        "y"
      ],
      headers: { "mcp-session-id" => "session-oversized" }
    )
    http = StreamingHttp.new(response)
    http.define_singleton_method(:finish) {}

    transport = TextStatsMcpClient::HttpTransport.allocate
    transport.instance_variable_set(:@endpoint, URI.parse("http://127.0.0.1:4570/mcp"))
    transport.instance_variable_set(:@timeout, 1.0)
    transport.instance_variable_set(:@token, TOKEN)
    transport.instance_variable_set(:@session_id, nil)
    transport.instance_variable_set(:@http, http)

    deleted_session = nil
    transport.define_singleton_method(:delete_session) { deleted_session = @session_id }

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      transport.send(
        :post,
        TextStatsMcpClient::Protocol.request(1, "initialize", {}),
        request_id: 1
      )
    end

    assert_equal 8, error.exit_code
    assert_equal "session-oversized", transport.instance_variable_get(:@session_id)
    transport.close
    assert_equal "session-oversized", deleted_session
  end

  def test_http_response_body_limit_is_enforced_while_streaming
    response = StreamingResponse.new([
      "x" * TextStatsMcpClient::MAX_RESPONSE_BYTES,
      "y"
    ])
    transport = TextStatsMcpClient::HttpTransport.allocate
    transport.instance_variable_set(:@timeout, 1.0)
    transport.instance_variable_set(:@http, StreamingHttp.new(response))

    error = assert_raises(TextStatsMcpClient::InvalidResultFailure) do
      transport.send(:perform, Net::HTTP::Get.new("/mcp"))
    end

    assert_equal 8, error.exit_code
    assert_equal 2, response.chunks_read
  end

  def test_http_cleanup_failure_is_not_reported_as_success
    transport = Class.new(FakeTransport) do
      define_method(:close) do
        raise TextStatsMcpClient::CapacityFailure, "HTTP 503 during MCP session cleanup"
      end
    end.new
    status = nil

    stdout, stderr = capture_io do
      status = TextStatsMcpClient::HttpTransport.stub(:new, transport) do
        TextStatsMcpClient.run(["--transport", "http", "server-info"])
      end
    end

    assert_equal 11, status
    assert_equal TextStatsMcpClient::PROTOCOL_VERSION, JSON.parse(stdout).fetch("mcpResult").fetch("protocolVersion")
    assert_includes stderr, "HTTP cleanup failure"
    assert_includes stderr, "HTTP 503 during MCP session cleanup"
  end

  def test_stdio_notifications_are_ignored_but_missing_or_mismatched_ids_fail
    notification_transport = stdio_transport_for(
      { "jsonrpc" => "2.0", "method" => "notifications/progress", "params" => {} },
      { "jsonrpc" => "2.0", "id" => 1, "result" => {} }
    )
    response = notification_transport.send(:read_response, 1)
    assert_equal 1, response.fetch("id")

    [
      { "jsonrpc" => "2.0", "result" => {} },
      { "jsonrpc" => "2.0", "id" => 99, "result" => {} }
    ].each do |message|
      transport = stdio_transport_for(message)
      error = assert_raises(TextStatsMcpClient::ProtocolFailure) do
        transport.send(:read_response, 1)
      end
      assert_equal 6, error.exit_code
    end
  end

  def test_stdio_shutdown_uses_fixed_two_second_grace_before_escalation
    transport = TextStatsMcpClient::StdioTransport.allocate
    waits = []
    signals = []
    transport.instance_variable_set(:@timeout, 0.1)
    transport.instance_variable_set(:@wait_thread, Object.new)
    transport.define_singleton_method(:wait_with_timeout) do |seconds|
      waits << seconds
      false
    end
    transport.define_singleton_method(:signal_process) do |signal|
      signals << signal
    end

    transport.send(:wait_for_exit)

    assert_equal [2.0, 1.0, 1.0], waits
    assert_equal ["TERM", "KILL"], signals
  end

  def test_protocol_error_and_tool_error_are_distinct
    json_rpc_error = assert_raises(TextStatsMcpClient::JsonRpcFailure) do
      TextStatsMcpClient::Protocol.result(
        { "jsonrpc" => "2.0", "id" => 1, "error" => { "code" => -32_601, "message" => "method not found" } },
        1
      )
    end
    assert_equal 6, json_rpc_error.exit_code

    tool_payload = {
      "contractVersion" => "1",
      "operation" => "tools/call",
      "mcpResult" => { "isError" => true, "content" => [{ "type" => "text", "text" => "invalid" }] }
    }
    tool_error = TextStatsMcpClient::ToolResultFailure.new(tool_payload)
    assert_equal 7, tool_error.exit_code
    assert_equal tool_payload, tool_error.payload
  end

  def test_tool_result_error_is_emitted_without_being_reclassified
    stdout, stderr, status = run_client(
      "tools",
      "call",
      "text_stats",
      "--arguments",
      JSON.generate({})
    )

    refute status.success?
    assert_equal 7, status.exitstatus
    assert_equal true, parse_response(stdout).fetch("mcpResult").fetch("isError")
    assert_includes stderr, "isError=true"
  end

  def test_http_client_matches_stdio_and_requires_external_authentication
    stdio_stdout, stdio_stderr, stdio_status = run_client(
      "tools",
      "call",
      "text_stats",
      "--arguments",
      JSON.generate("text" => "alpha beta\n")
    )
    assert stdio_status.success?, stdio_stderr

    server = HttpServerProcess.new
    http_stdout, http_stderr, http_status = run_client(
      "--transport",
      "http",
      "--endpoint",
      "http://127.0.0.1:#{server.port}/mcp",
      "tools",
      "call",
      "text_stats",
      "--arguments",
      JSON.generate("text" => "alpha beta\n"),
      env: { "TEXT_STATS_MCP_HTTP_TOKEN" => TOKEN }
    )
    assert http_status.success?, http_stderr
    assert_equal(
      parse_response(stdio_stdout).fetch("mcpResult").fetch("structuredContent"),
      parse_response(http_stdout).fetch("mcpResult").fetch("structuredContent")
    )

    no_token_stdout, no_token_stderr, no_token_status = run_client(
      "--transport",
      "http",
      "--endpoint",
      "http://127.0.0.1:#{server.port}/mcp",
      "server-info"
    )
    refute no_token_status.success?
    assert_equal 4, no_token_status.exitstatus
    assert_equal "", no_token_stdout
    refute_includes no_token_stderr, TOKEN
  ensure
    server&.stop
  end

  def test_http_endpoint_and_transport_failures_are_distinct
    invalid_stdout, invalid_stderr, invalid_status = run_client(
      "--transport",
      "http",
      "--endpoint",
      "http://example.test/mcp",
      "server-info",
      env: { "TEXT_STATS_MCP_HTTP_TOKEN" => TOKEN }
    )
    refute invalid_status.success?
    assert_equal 2, invalid_status.exitstatus
    assert_equal "", invalid_stdout
    assert_includes invalid_stderr, "127.0.0.1"

    port = HttpServerProcess.free_port
    transport_stdout, transport_stderr, transport_status = run_client(
      "--transport",
      "http",
      "--endpoint",
      "http://127.0.0.1:#{port}/mcp",
      "server-info",
      env: { "TEXT_STATS_MCP_HTTP_TOKEN" => TOKEN }
    )
    refute transport_status.success?
    assert_equal 3, transport_status.exitstatus
    assert_equal "", transport_stdout
    assert_includes transport_stderr, "transport failure"
  end

  def test_http_timeout_is_bounded_and_does_not_expose_token
    server = HttpServerProcess.new(
      extra_environment: {
        "TEXT_STATS_MCP_TEST_MODE" => "1",
        "TEXT_STATS_MCP_TEST_TOOL_DELAY" => "1"
      }
    )
    stdout, stderr, status = run_client(
      "--transport",
      "http",
      "--endpoint",
      "http://127.0.0.1:#{server.port}/mcp",
      "--timeout",
      "0.1",
      "tools",
      "call",
      "text_stats",
      "--arguments",
      JSON.generate("text" => "bounded"),
      env: { "TEXT_STATS_MCP_HTTP_TOKEN" => TOKEN }
    )
    refute status.success?
    assert_equal 5, status.exitstatus
    assert_equal "", stdout
    assert_includes stderr, "timeout"
    refute_includes stderr, TOKEN
  ensure
    server&.stop
  end
end
