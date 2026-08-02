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
        run_test_delay(server_context)

        result = TextStatsMcp.analyze(text)
        MCP::Tool::Response.new(
          [{ type: "text", text: JSON.generate(result) }],
          structured_content: result
        )
      end

      private

      def run_test_delay(server_context)
        return unless ENV["TEXT_STATS_MCP_TEST_MODE"] == "1"

        delay_text = ENV["TEXT_STATS_MCP_TEST_TOOL_DELAY"]
        return unless delay_text

        delay = Float(delay_text)
        raise ArgumentError, "test tool delay must be nonnegative" if delay.negative?

        marker = ENV["TEXT_STATS_MCP_TEST_TOOL_MARKER"]
        File.binwrite(marker, "started\n") if marker

        deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + delay
        loop do
          server_context.raise_if_cancelled!
          remaining = deadline - Process.clock_gettime(Process::CLOCK_MONOTONIC)
          break unless remaining.positive?

          sleep [remaining, 0.01].min
        end
      ensure
        File.binwrite(marker, "finished\n") if marker
      end
    end
  end

  class SelectedRevisionServer < MCP::Server
    private

    def init(params, session: nil)
      requested_revision = params[:protocolVersion] if params.is_a?(Hash)
      negotiated_params = if requested_revision.is_a?(String) && requested_revision != PROTOCOL_VERSION
                            params.merge(protocolVersion: PROTOCOL_VERSION)
                          else
                            params
                          end

      super(negotiated_params, session: session)
    end
  end

  module_function

  def build_server
    configuration = MCP::Configuration.new(
      protocol_version: PROTOCOL_VERSION,
      validate_tool_call_arguments: true,
      validate_tool_call_results: true
    )

    SelectedRevisionServer.new(
      name: "text_stats_fixture",
      version: VERSION,
      instructions: "Call text_stats with one string-valued text argument.",
      tools: [TextStatsTool],
      capabilities: { tools: { listChanged: false } },
      configuration: configuration
    )
  end
end
