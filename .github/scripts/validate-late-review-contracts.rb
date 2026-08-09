#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "lib/profile-contracts"

selection = ProfileSelection.load
repository = RepositorySnapshot.new
selected_profiles = selection.profiles.to_set
errors = []

ignored_root_names = Set.new(%w[
  README.md
  SKILL.md
  AGENTS.md
  CONTRIBUTING.md
  RUNTIME.md
  INTERFACES.md
  CLI_INTERFACE.md
  MCP_INTERFACE.md
  WEB_INTERFACE.md
  LICENSE
  LICENSE.md
  LICENSE.template
  COPYING
  COPYING.md
  SECURITY.md
  CODE_OF_CONDUCT.md
  CHANGELOG.md
].map(&:downcase)).freeze

guidance_extensions = Set.new(%w[.md .markdown .mdx .rst .adoc .asciidoc .txt .pdf]).freeze
root_implementation_files = repository.root_files.select do |path|
  !path.start_with?(".") &&
    !ignored_root_names.include?(path.downcase) &&
    !guidance_extensions.include?(File.extname(path).downcase)
end

if selection.template_scaffold? && !root_implementation_files.empty?
  errors << "'template-scaffold' cannot be retained after adding language-neutral root implementation signals: #{root_implementation_files.sort.join(', ')}."
elsif !selection.template_scaffold?
  application_profiles = Set.new(%w[packaged-cli mcp-enabled browser-interface headless-service])
  if !root_implementation_files.empty? && selected_profiles.disjoint?(application_profiles)
    errors << "Language-neutral root implementation files require an application or service profile: #{root_implementation_files.sort.join(', ')}."
  end
end

if selection.selected?("mcp-enabled")
  runtime = repository.document("RUNTIME.md")
  if runtime
    protocol = runtime.section("## MCP protocol support")
    revisions = runtime.table_value("Supported protocol revisions", section: protocol) || ""

    stdio = runtime.section("### stdio variant")
    if runtime.table_value("Supported", section: stdio) == "YES"
      [
        "Server entry point",
        "Lifecycle owner",
        "Invocation scope",
        "Protocol negotiation/discovery",
        "Request metadata behavior",
        "Startup cost policy",
        "Cancellation behavior",
        "Child-process shutdown and escalation"
      ].each do |item|
        unless ValuePolicy.concrete?(runtime.table_value(item, section: stdio))
          errors << "Supported stdio requires a concrete '#{item}' runtime value; NOT SUPPORTED is reserved for Supported: NO."
        end
      end
    end

    http = runtime.section("### Streamable HTTP variant")
    http_supported = runtime.table_value("Supported", section: http) == "YES"
    if http_supported
      [
        "Server entry point",
        "Endpoint path",
        "Default bind address",
        "Port",
        "Supported protocol eras",
        "Revision-specific state model",
        "Concurrent-client policy",
        "Authentication",
        "Host-header validation",
        "Origin validation granularity",
        "Allowed origins and absent-Origin policy",
        "Connection-reuse security tests",
        "Readiness check",
        "Cancellation behavior",
        "Shutdown/restart policy",
        "Non-loopback support"
      ].each do |item|
        unless ValuePolicy.concrete?(runtime.table_value(item, section: http))
          errors << "Supported Streamable HTTP requires a concrete '#{item}' runtime value; NOT SUPPORTED is reserved for Supported: NO."
        end
      end
    end

    if http_supported && revisions.include?("2026-07-28")
      # Modern transport row labels are unique within the Streamable HTTP
      # section. Read them from that authoritative section directly rather
      # than coupling validation to surrounding explanatory prose.
      [
        "POST request model",
        "`Accept: application/json, text/event-stream`",
        "`MCP-Protocol-Version` and request `_meta` consistency",
        "Required `Mcp-Method` and conditional `Mcp-Name` headers",
        "Header value encoding",
        "`x-mcp-header` validation and `Mcp-Param-*` emission",
        "JSON and request-scoped SSE response handling",
        "SSE-stream cancellation",
        "`Mcp-Session-Id`, GET, DELETE, and resumability"
      ].each do |item|
        unless ValuePolicy.concrete?(runtime.table_value(item, section: http))
          errors << "Protocol revision 2026-07-28 with Streamable HTTP requires a concrete modern transport value for '#{item}'."
        end
      end

      fallback = runtime.table_value("Initialization-era fallback on the same endpoint", section: http)
      unless ValuePolicy.resolved_allow_not_supported?(fallback)
        errors << "Protocol revision 2026-07-28 requires a resolved initialization-era fallback decision; NOT SUPPORTED is allowed, NONE is not."
      end
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Late-review Agent Skill contracts are valid."
