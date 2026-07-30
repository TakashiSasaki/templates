#!/usr/bin/env ruby

require "yaml"

skill_path = "SKILL.md"
unless File.file?(skill_path)
  warn "Missing universally required file: SKILL.md"
  exit 1
end

lines = File.readlines(skill_path, chomp: true)
text = lines.join("\n")

strip_backticks = lambda do |value|
  normalized = value.to_s.strip
  if normalized.length >= 2 && normalized.start_with?("`") && normalized.end_with?("`")
    normalized[1...-1]
  else
    normalized
  end
end

resolved_value = lambda do |value|
  value && !value.strip.empty? && !/\b(?:TODO|UNSELECTED)\b/i.match?(value)
end

concrete_value = lambda do |value|
  resolved_value.call(value) && !/\A(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE))\z/i.match?(value.strip)
end

resolved_allow_not_supported = lambda do |value|
  resolved_value.call(value) && !/\A(?:NONE|NOT\s+APPLICABLE)\z/i.match?(value.strip)
end

markdown_section = lambda do |document, heading|
  level = heading[/\A#+/].length
  boundary = level == 2 ? "^##\\s|\\z" : "^(?:##|###)\\s|\\z"
  match = document.match(
    Regexp.new("^#{Regexp.escape(heading)}\\s*$\\n(.*?)(?=#{boundary})", Regexp::MULTILINE)
  )
  match && match[1]
end

table_value = lambda do |section, item|
  match = section&.match(/^\|\s*#{Regexp.escape(item)}\s*\|\s*(.*?)\s*\|\s*$/)
  match && strip_backticks.call(match[1])
end

profile_values = lines.filter_map do |raw_line|
  normalized = raw_line.strip
  normalized = normalized[2..].strip if normalized.start_with?("- ")
  match = normalized.match(/\ASelected profiles:\s*(.+?)\s*\z/)
  strip_backticks.call(match[1]) if match
end

errors = []

if profile_values.length != 1
  errors << "SKILL.md must contain exactly one 'Selected profiles:' declaration."
else
  selected_profiles = profile_values.first.split(",").map(&:strip).reject(&:empty?)
  template_scaffold = selected_profiles == ["template-scaffold"]

  ignored_root_names = %w[
    README.md SKILL.md AGENTS.md CONTRIBUTING.md RUNTIME.md INTERFACES.md WEB_INTERFACE.md
    LICENSE LICENSE.md LICENSE.template COPYING COPYING.md SECURITY.md CODE_OF_CONDUCT.md CHANGELOG.md
  ]
  guidance_extensions = %w[.md .markdown .mdx .rst .adoc .asciidoc .txt .pdf]

  root_implementation_files = Dir.children(".").select do |path|
    next false if path.start_with?(".")
    next false unless File.file?(path) && !File.symlink?(path)
    next false if ignored_root_names.any? { |name| path.casecmp?(name) }
    next false if guidance_extensions.include?(File.extname(path).downcase)

    true
  end

  if template_scaffold && !root_implementation_files.empty?
    errors << "'template-scaffold' cannot be retained after adding language-neutral root implementation signals: #{root_implementation_files.sort.join(', ')}."
  elsif !template_scaffold
    application_profiles = %w[packaged-cli mcp-enabled browser-interface headless-service]
    if !root_implementation_files.empty? && (selected_profiles & application_profiles).empty?
      errors << "Language-neutral root implementation files require an application or service profile: #{root_implementation_files.sort.join(', ')}."
    end
  end

  if selected_profiles.include?("mcp-enabled") && File.file?("RUNTIME.md")
    runtime = File.read("RUNTIME.md")
    protocol = markdown_section.call(runtime, "## MCP protocol support")
    revisions = table_value.call(protocol, "Supported protocol revisions").to_s

    stdio = markdown_section.call(runtime, "### stdio variant")
    if table_value.call(stdio, "Supported") == "YES"
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
        unless concrete_value.call(table_value.call(stdio, item))
          errors << "Supported stdio requires a concrete '#{item}' runtime value; NOT SUPPORTED is reserved for Supported: NO."
        end
      end
    end

    http = markdown_section.call(runtime, "### Streamable HTTP variant")
    http_supported = table_value.call(http, "Supported") == "YES"
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
        unless concrete_value.call(table_value.call(http, item))
          errors << "Supported Streamable HTTP requires a concrete '#{item}' runtime value; NOT SUPPORTED is reserved for Supported: NO."
        end
      end
    end

    if http_supported && revisions.include?("2026-07-28")
      modern_table = http&.match(
        /When `2026-07-28` is supported, also complete:\s*\n\n(.*?)(?=\nThe stdio and Streamable HTTP variants|\z)/m
      )&.[](1)

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
        unless concrete_value.call(table_value.call(modern_table, item))
          errors << "Protocol revision 2026-07-28 with Streamable HTTP requires a concrete modern transport value for '#{item}'."
        end
      end

      fallback = table_value.call(modern_table, "Initialization-era fallback on the same endpoint")
      unless resolved_allow_not_supported.call(fallback)
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
