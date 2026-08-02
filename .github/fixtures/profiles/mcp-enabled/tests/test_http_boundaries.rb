# frozen_string_literal: true

require "minitest/autorun"
require "rack/mock"
require "timeout"
require_relative "../mcp/http_server"

class TextStatsMcpHttpBoundariesTest < Minitest::Test
  HOST = "127.0.0.1"

  class FakeTransport
    def call(_env)
      [200, { "content-type" => "application/json" }, ["{}"]]
    end
  end

  class FakeServer
    def initialize(queue)
      @queue = queue
    end

    def shutdown
      @queue << :shutdown
    end
  end

  def application(port)
    TextStatsMcp::HttpApplication.new(
      transport: FakeTransport.new,
      host: HOST,
      port: port,
      token_matcher: ->(_request) { true }
    )
  end

  def test_port_80_accepts_canonical_default_port_forms
    request = Rack::MockRequest.new(application(80))

    implicit = request.get(
      "/readyz",
      "HTTP_HOST" => HOST,
      "HTTP_ORIGIN" => "http://#{HOST}"
    )
    assert_equal 200, implicit.status

    explicit = request.get(
      "/readyz",
      "HTTP_HOST" => "#{HOST}:80",
      "HTTP_ORIGIN" => "http://#{HOST}:80"
    )
    assert_equal 200, explicit.status

    wrong_port = request.get(
      "/readyz",
      "HTTP_HOST" => "#{HOST}:81",
      "HTTP_ORIGIN" => "http://#{HOST}:81"
    )
    assert_equal 403, wrong_port.status

    assert_equal "http://#{HOST}", TextStatsMcp.endpoint_origin(HOST, 80)
  end

  def test_nondefault_port_requires_the_explicit_authority
    request = Rack::MockRequest.new(application(4570))

    accepted = request.get(
      "/readyz",
      "HTTP_HOST" => "#{HOST}:4570",
      "HTTP_ORIGIN" => "http://#{HOST}:4570"
    )
    assert_equal 200, accepted.status

    missing_port = request.get(
      "/readyz",
      "HTTP_HOST" => HOST,
      "HTTP_ORIGIN" => "http://#{HOST}"
    )
    assert_equal 403, missing_port.status
  end

  def test_pending_shutdown_is_delivered_when_server_attaches
    queue = Queue.new
    coordinator = TextStatsMcp::ShutdownCoordinator.new

    coordinator.request
    assert coordinator.attach(FakeServer.new(queue))
    assert_equal :shutdown, Timeout.timeout(1) { queue.pop }
  end

  def test_shutdown_after_attachment_is_delivered
    queue = Queue.new
    coordinator = TextStatsMcp::ShutdownCoordinator.new

    refute coordinator.attach(FakeServer.new(queue))
    coordinator.request
    assert_equal :shutdown, Timeout.timeout(1) { queue.pop }
  end
end
