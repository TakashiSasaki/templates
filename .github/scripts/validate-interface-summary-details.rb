#!/usr/bin/env ruby
# frozen_string_literal: true

require "uri"

SKILL_PATH = "SKILL.md"
CLI_PATH = "CLI_INTERFACE.md"
MCP_PATH = "MCP_INTERFACE.md"
RUNTIME_PATH = "RUNTIME.md"

unless File.file?(SKILL_PATH)
  warn "Missing universally required file: #{SKILL_PATH}"
  exit 1
end

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

runtime_reference = lambda do |value|
  /\Asee\s+RUNTIME\.md\z/i.match?(value.to_s.strip)
end

markdown_section = lambda do |document, heading|
  level = heading[/\A#+/].length
  boundary = level == 2 ? "^##\\s|\\z" : "^(?:##|###)\\s|\\z"
  match = document.match(
    Regexp.new("^#{Regexp.escape(heading)}\\s*$\\n(.*?)(?=#{boundary})", Regexp::MULTILINE)
  )
  match && match[1]
end

field_value = lambda do |section, label|
  match = section&.match(/^#{Regexp.escape(label)}:\s*(.*?)\s*$/)
  match && strip_backticks.call(match[1])
end

table_value = lambda do |section, item|
  match = section&.match(/^\|\s*#{Regexp.escape(item)}\s*\|\s*(.*?)\s*\|\s*$/)
  match && strip_backticks.call(match[1])
end

support_token = lambda do |value|
  value&.strip&.split(/[;\s]/)&.first&.upcase
end

summary_values = lambda do |lines, label|
  lines.filter_map do |raw_line|
    normalized = raw_line.strip
    normalized = normalized[2..].strip if normalized.start_with?("- ")
    match = normalized.match(/\A#{Regexp.escape(label)}:\s*(.+?)\s*\z/)
    strip_backticks.call(match[1]) if match
  end
end

skill_lines = File.readlines(SKILL_PATH, chomp: true)
profile_values = summary_values.call(skill_lines, "Selected profiles")
if profile_values.length != 1
  warn "#{SKILL_PATH} must contain exactly one 'Selected profiles:' declaration."
  exit 1
end

selected_profiles = profile_values.first.split(",").map(&:strip).reject(&:empty?)
if selected_profiles == ["template-scaffold"]
  puts "Interface summary details are valid for the template scaffold."
  exit 0
end

errors = []

if selected_profiles.include?("packaged-cli")
  unless File.file?(CLI_PATH)
    errors << "Selected profile 'packaged-cli' requires #{CLI_PATH}."
  else
    cli = File.read(CLI_PATH)
    cli_working_directory = field_value.call(
      markdown_section.call(cli, "## Human CLI"),
      "Working directory"
    )
    skill_working_directories = summary_values.call(skill_lines, "Working directory")

    if skill_working_directories.length != 1
      errors << "Selected profile 'packaged-cli' requires exactly one 'Working directory:' summary in #{SKILL_PATH}."
    elsif !concrete_value.call(skill_working_directories.first)
      errors << "#{SKILL_PATH} requires a concrete packaged-CLI 'Working directory:' summary."
    elsif !concrete_value.call(cli_working_directory)
      errors << "#{CLI_PATH} requires a concrete packaged-CLI 'Working directory:' value."
    elsif skill_working_directories.first != cli_working_directory
      errors << "Packaged CLI working directory must match between #{SKILL_PATH} and #{CLI_PATH}: " \
                "#{skill_working_directories.first.inspect} != #{cli_working_directory.inspect}."
    end
  end
end

if selected_profiles.include?("mcp-enabled")
  unless File.file?(MCP_PATH)
    errors << "Selected profile 'mcp-enabled' requires #{MCP_PATH}."
  end
  unless File.file?(RUNTIME_PATH)
    errors << "Selected profile 'mcp-enabled' requires #{RUNTIME_PATH}."
  end

  if File.file?(MCP_PATH) && File.file?(RUNTIME_PATH)
    mcp = File.read(MCP_PATH)
    runtime = File.read(RUNTIME_PATH)
    public_http = markdown_section.call(mcp, "## Streamable HTTP MCP server variant")
    runtime_http = markdown_section.call(runtime, "### Streamable HTTP variant")

    if support_token.call(field_value.call(public_http, "Supported")) == "YES"
      endpoint = field_value.call(public_http, "Endpoint URL")

      unless concrete_value.call(endpoint)
        errors << "Supported Streamable HTTP requires a concrete 'Endpoint URL:' or 'see RUNTIME.md'."
      else
        unless runtime_reference.call(endpoint)
          runtime_bind = table_value.call(runtime_http, "Default bind address")
          runtime_port = table_value.call(runtime_http, "Port")
          runtime_path = table_value.call(runtime_http, "Endpoint path")

          [
            ["Default bind address", runtime_bind],
            ["Port", runtime_port],
            ["Endpoint path", runtime_path]
          ].each do |label, value|
            unless concrete_value.call(value)
              errors << "Concrete Streamable HTTP Endpoint URL requires a concrete '#{label}' in #{RUNTIME_PATH}; " \
                        "otherwise use 'Endpoint URL: see RUNTIME.md'."
            end
          end

          if concrete_value.call(runtime_bind) && concrete_value.call(runtime_port) && concrete_value.call(runtime_path)
            unless /\A\d+\z/.match?(runtime_port) && (1..65_535).cover?(runtime_port.to_i)
              errors << "Concrete Streamable HTTP Endpoint URL requires a fixed numeric runtime port; " \
                        "otherwise use 'Endpoint URL: see RUNTIME.md'."
            else
              begin
                uri = URI.parse(endpoint)
                unless uri.is_a?(URI::HTTP) && uri.host
                  errors << "Streamable HTTP Endpoint URL must be an absolute http or https URL."
                else
                  public_host = uri.host.to_s.sub(/\A\[(.*)\]\z/, "\\1")
                  authoritative_host = runtime_bind.to_s.sub(/\A\[(.*)\]\z/, "\\1")
                  wildcard_bind = %w[0.0.0.0 ::].include?(authoritative_host)

                  if !wildcard_bind && public_host != authoritative_host
                    errors << "Streamable HTTP Endpoint URL host must match #{RUNTIME_PATH}: " \
                              "#{public_host.inspect} != #{authoritative_host.inspect}."
                  end
                  if uri.port != runtime_port.to_i
                    errors << "Streamable HTTP Endpoint URL port must match #{RUNTIME_PATH}: " \
                              "#{uri.port.inspect} != #{runtime_port.to_i.inspect}."
                  end
                  if uri.path != runtime_path
                    errors << "Streamable HTTP Endpoint URL path must match #{RUNTIME_PATH}: " \
                              "#{uri.path.inspect} != #{runtime_path.inspect}."
                  end
                  if uri.query || uri.fragment
                    errors << "Streamable HTTP Endpoint URL must not add a query or fragment to the runtime endpoint path."
                  end
                end
              rescue URI::InvalidURIError
                errors << "Streamable HTTP Endpoint URL is not a valid URI: #{endpoint.inspect}."
              end
            end
          end
        end
      end
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Interface summary details are consistent."
