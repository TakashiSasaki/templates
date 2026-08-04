#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "net/http"

host = "127.0.0.1"
port = Integer(ENV.fetch("TEXT_STATS_MCP_HTTP_PORT"), 10)
token = File.binread(ENV.fetch("TEXT_STATS_MCP_SMOKE_TOKEN_FILE")).sub(/\r?\n\z/, "")
accept = "application/json, text/event-stream"
http = Net::HTTP.new(host, port, nil)
http.open_timeout = 2
http.read_timeout = 2

request = Net::HTTP::Post.new("/mcp")
request["Accept"] = accept
request["Content-Type"] = "application/json"
request["Authorization"] = "Bearer #{token}"
request.body = JSON.generate(
  jsonrpc: "2.0",
  method: "initialize",
  id: 1,
  params: {
    protocolVersion: "2025-11-25",
    capabilities: {},
    clientInfo: { name: "systemd-smoke", version: "1.0.0" }
  }
)
response = http.request(request)
raise "initialize failed: #{response.code} #{response.body}" unless response.code == "200"
session = response["mcp-session-id"]
raise "missing session" if session.to_s.empty?

notify = Net::HTTP::Post.new("/mcp")
notify["Accept"] = accept
notify["Content-Type"] = "application/json"
notify["Authorization"] = "Bearer #{token}"
notify["Mcp-Session-Id"] = session
notify["MCP-Protocol-Version"] = "2025-11-25"
notify.body = JSON.generate(jsonrpc: "2.0", method: "notifications/initialized", params: {})
response = http.request(notify)
raise "initialized notification failed: #{response.code}" unless response.code == "202"

inventory = Net::HTTP::Post.new("/mcp")
inventory["Accept"] = accept
inventory["Content-Type"] = "application/json"
inventory["Authorization"] = "Bearer #{token}"
inventory["Mcp-Session-Id"] = session
inventory["MCP-Protocol-Version"] = "2025-11-25"
inventory.body = JSON.generate(jsonrpc: "2.0", method: "tools/list", id: 2, params: {})
response = http.request(inventory)
tools = JSON.parse(response.body).fetch("result").fetch("tools")
raise "unexpected inventory" unless tools.map { |tool| tool.fetch("name") } == ["text_stats"]

results = [[3, "alpha beta\n", { "bytes" => 11, "lines" => 1, "words" => 2 }],
           [4, "gamma\ndelta\n", { "bytes" => 12, "lines" => 2, "words" => 2 }]].map do |id, text, expected|
  call = Net::HTTP::Post.new("/mcp")
  call["Accept"] = accept
  call["Content-Type"] = "application/json"
  call["Authorization"] = "Bearer #{token}"
  call["Mcp-Session-Id"] = session
  call["MCP-Protocol-Version"] = "2025-11-25"
  call.body = JSON.generate(
    jsonrpc: "2.0",
    method: "tools/call",
    id: id,
    params: { name: "text_stats", arguments: { text: text } }
  )
  response = http.request(call)
  result = JSON.parse(response.body).fetch("result").fetch("structuredContent")
  raise "unexpected result: #{result.inspect}" unless result == expected
  result
end

puts JSON.generate(ok: true, tools: tools.map { |tool| tool.fetch("name") }, results: results)
