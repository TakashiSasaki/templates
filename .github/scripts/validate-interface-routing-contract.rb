#!/usr/bin/env ruby
# frozen_string_literal: true

SKILL_PATH = "SKILL.md"
ROUTING_PATH = "INTERFACES.md"
PUBLIC_INTERFACE_PROFILES = %w[packaged-cli mcp-enabled].freeze
ROUTE_LABELS = [
  "native MCP tool already registered in the host",
  "existing Streamable HTTP MCP endpoint",
  "bundled ad hoc MCP tool client over stdio or Streamable HTTP",
  "stable in-place CLI launcher",
  "installed human CLI command"
].freeze

unless File.file?(SKILL_PATH)
  warn "Missing universally required file: SKILL.md"
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

normalize_route = lambda do |value|
  value.to_s.strip.gsub(/\s+/, " ").downcase
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

support_token = lambda do |value|
  value&.strip&.split(/[;\s]/)&.first&.upcase
end

profile_values = File.readlines(SKILL_PATH, chomp: true).filter_map do |raw_line|
  normalized = raw_line.strip
  normalized = normalized[2..].strip if normalized.start_with?("- ")
  match = normalized.match(/\ASelected profiles:\s*(.+?)\s*\z/)
  strip_backticks.call(match[1]) if match
end

if profile_values.length != 1
  warn "SKILL.md must contain exactly one 'Selected profiles:' declaration."
  exit 1
end

selected_profiles = profile_values.first.split(",").map(&:strip).reject(&:empty?)
if selected_profiles == ["template-scaffold"]
  puts "Public interface routing contract is valid for the template scaffold."
  exit 0
end

routing_selected = (selected_profiles & PUBLIC_INTERFACE_PROFILES).any?
errors = []

if !routing_selected && File.exist?(ROUTING_PATH)
  errors << "Retained contract #{ROUTING_PATH} is unsupported without packaged-cli or mcp-enabled."
elsif routing_selected
  unless File.file?(ROUTING_PATH)
    errors << "Selected public-interface profiles require contract file: #{ROUTING_PATH}"
  else
    document = File.read(ROUTING_PATH)
    required_headings = [
      "## Status",
      "## Execution policy",
      "## Contract index",
      "## Cross-interface invariants",
      "## Availability and failure behavior",
      "## Decision rationale"
    ]

    required_headings.each do |heading|
      section = markdown_section.call(document, heading)
      if section.nil? || section.strip.empty?
        errors << "Selected routing contract #{ROUTING_PATH} requires non-empty section '#{heading}'."
      end
    end

    status = field_value.call(markdown_section.call(document, "## Status"), "Selection status")
    unless status == "SELECTED"
      errors << "Selected routing contract #{ROUTING_PATH} requires 'Selection status: SELECTED'."
    end

    if /\b(?:TODO|UNSELECTED)\b/i.match?(document)
      errors << "Selected routing contract #{ROUTING_PATH} must not retain TODO or UNSELECTED placeholders."
    end

    cli = File.file?("CLI_INTERFACE.md") ? File.read("CLI_INTERFACE.md") : nil
    mcp = File.file?("MCP_INTERFACE.md") ? File.read("MCP_INTERFACE.md") : nil

    cli_launcher_support = if cli
                             support_token.call(
                               field_value.call(
                                 markdown_section.call(cli, "## In-place agent launcher"),
                                 "Supported"
                               )
                             )
                           end
    mcp_stdio_support = if mcp
                         support_token.call(
                           field_value.call(
                             markdown_section.call(mcp, "## stdio MCP server variant"),
                             "Supported"
                           )
                         )
                       end
    mcp_http_support = if mcp
                        support_token.call(
                          field_value.call(
                            markdown_section.call(mcp, "## Streamable HTTP MCP server variant"),
                            "Supported"
                          )
                        )
                      end
    mcp_client_support = if mcp
                          support_token.call(
                            field_value.call(
                              markdown_section.call(mcp, "## Bundled ad hoc MCP tool client"),
                              "Supported"
                            )
                          )
                        end

    canonical_routes = ROUTE_LABELS.to_h { |label| [normalize_route.call(label), label] }
    route_available = lambda do |canonical|
      case canonical
      when "installed human CLI command"
        selected_profiles.include?("packaged-cli") && !cli.nil?
      when "stable in-place CLI launcher"
        selected_profiles.include?("packaged-cli") && cli_launcher_support == "YES"
      when "native MCP tool already registered in the host"
        selected_profiles.include?("mcp-enabled") &&
          !mcp.nil? &&
          [mcp_stdio_support, mcp_http_support].include?("YES")
      when "existing Streamable HTTP MCP endpoint"
        selected_profiles.include?("mcp-enabled") && mcp_http_support == "YES"
      when "bundled ad hoc MCP tool client over stdio or Streamable HTTP"
        selected_profiles.include?("mcp-enabled") && mcp_client_support == "YES"
      else
        false
      end
    end

    validate_route = lambda do |label, value, allow_none|
      unless resolved_value.call(value)
        errors << "#{ROUTING_PATH} requires a resolved '#{label}:' value."
        next nil
      end

      normalized = normalize_route.call(value)
      if normalized == "none"
        unless allow_none
          errors << "#{ROUTING_PATH} cannot use NONE as the preferred agent interface."
        end
        next "NONE"
      end

      canonical = canonical_routes[normalized]
      unless canonical
        errors << "#{ROUTING_PATH} '#{label}:' must use one documented route category exactly."
        next nil
      end

      unless route_available.call(canonical)
        errors << "#{ROUTING_PATH} route '#{canonical}' is not implemented by the selected profiles and support declarations."
      end

      canonical
    end

    execution = markdown_section.call(document, "## Execution policy")
    preferred = validate_route.call(
      "Preferred agent interface",
      field_value.call(execution, "Preferred agent interface"),
      false
    )
    fallback_1 = validate_route.call("Fallback 1", field_value.call(execution, "Fallback 1"), true)
    fallback_2 = validate_route.call("Fallback 2", field_value.call(execution, "Fallback 2"), true)

    if fallback_1 == "NONE" && fallback_2 && fallback_2 != "NONE"
      errors << "#{ROUTING_PATH} cannot define Fallback 2 after Fallback 1 is NONE."
    end

    concrete_routes = [preferred, fallback_1, fallback_2].compact.reject { |route| route == "NONE" }
    duplicates = concrete_routes.tally.select { |_route, count| count > 1 }.keys
    unless duplicates.empty?
      errors << "#{ROUTING_PATH} must not repeat a route in the preferred/fallback order: #{duplicates.join(', ')}."
    end

    availability = markdown_section.call(document, "## Availability and failure behavior")
    [
      "Unavailable preferred interface behavior",
      "Fallback activation conditions",
      "Failure classification exposed to callers"
    ].each do |label|
      unless concrete_value.call(field_value.call(availability, label))
        errors << "#{ROUTING_PATH} requires a concrete '#{label}:' value."
      end
    end

    rationale = markdown_section.call(document, "## Decision rationale")
    unless concrete_value.call(field_value.call(rationale, "Rationale"))
      errors << "#{ROUTING_PATH} requires a concrete 'Rationale:' value."
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Public interface routing contract is valid."
