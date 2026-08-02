# frozen_string_literal: true

require "mcp"
require_relative "server_factory"

$stderr.sync = true
warn "text-stats MCP stdio server starting"

transport = MCP::Server::Transports::StdioTransport.new(TextStatsMcp.build_server)
begin
  transport.open
ensure
  warn "text-stats MCP stdio server stopped"
end
