# frozen_string_literal: true

require "json"
require "mcp"
require_relative "../src/text_stats"

module TextStatsMcp
  class TextStatsTool < MCP::Tool
    tool_name TOOL_NAME
    description "Compute deterministic byte, line, and word counts for UTF-8 text."
    input_schema(
      properties: {
        text: {
          type: "string",
          description: "UTF-8 text to analyze"
        }
      },
      required: ["text"],
      additionalProperties: false
    )
    output_schema(
      properties: {
        bytes: { type: "integer", minimum: 0 },
        lines: { type: "integer", minimum: 0 },
        words: { type: "integer", minimum: 0 }
      },
      required: %w[bytes lines words],
      additionalProperties: false
    )
    annotations(
      destructive_hint: false,
      idempotent_hint: true,
      open_world_hint: false,
      read_only_hint: true
    )

    class << self
      def call(text:, server_context:)
        result = TextStatsMcp.analyze(text)
        MCP::Tool::Response.new(
          [{ type: "text", text: JSON.generate(result) }],
          structured_content: result
        )
      end
    end
  end

  class FixedRevisionServer < MCP::Server
    private

    def init(params, session: nil)
      if params.is_a?(Hash) && params[:protocolVersion] != PROTOCOL_VERSION
        raise MCP::Server::RequestHandlerError.new(
          "Unsupported protocol version: #{params[:protocolVersion].inspect}",
          params,
          error_type: :invalid_params
        )
      end

      super
    end
  end

  module_function

  def build_server
    configuration = MCP::Configuration.new(
      protocol_version: PROTOCOL_VERSION,
      validate_tool_call_arguments: true,
      validate_tool_call_results: true
    )

    FixedRevisionServer.new(
      name: "text_stats_fixture",
      version: VERSION,
      instructions: "Call text_stats with one string-valued text argument.",
      tools: [TextStatsTool],
      capabilities: { tools: { listChanged: false } },
      configuration: configuration
    )
  end
end

$stderr.sync = true
warn "text-stats MCP stdio server starting"

transport = MCP::Server::Transports::StdioTransport.new(TextStatsMcp.build_server)
begin
  transport.open
ensure
  warn "text-stats MCP stdio server stopped"
end
