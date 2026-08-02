#!/usr/bin/env ruby
# frozen_string_literal: true

SKILL_PATH = "SKILL.md"
RUNTIME_PATH = "RUNTIME.md"

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

skill_lines = File.readlines(SKILL_PATH, chomp: true)
profile_values = skill_lines.filter_map do |raw_line|
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
  puts "Public interface and runtime contracts are consistent for the template scaffold."
  exit 0
end

checked_profiles = selected_profiles & %w[packaged-cli mcp-enabled]
if checked_profiles.empty?
  puts "No packaged CLI or MCP consistency checks are activated."
  exit 0
end

errors = []

unless File.file?(RUNTIME_PATH)
  errors << "Selected public-interface profiles require runtime authority: #{RUNTIME_PATH}"
end

runtime = File.file?(RUNTIME_PATH) ? File.read(RUNTIME_PATH) : nil

compare_commands = lambda do |label, public_value, authoritative_value, authority|
  unless concrete_value.call(public_value)
    errors << "#{label} requires a concrete caller-visible command."
    next
  end
  unless concrete_value.call(authoritative_value)
    errors << "#{label} requires a concrete matching command in #{authority}."
    next
  end
  next if public_value == authoritative_value

  errors << "#{label} must match #{authority} exactly: #{public_value.inspect} != #{authoritative_value.inspect}."
end

compare_selections = lambda do |label, public_value, runtime_value|
  unless concrete_value.call(public_value)
    errors << "#{label} requires a concrete caller-visible value or 'see RUNTIME.md'."
    next
  end
  unless concrete_value.call(runtime_value)
    errors << "#{label} requires a concrete authoritative value in #{RUNTIME_PATH}."
    next
  end
  next if runtime_reference.call(public_value) || public_value == runtime_value

  errors << "#{label} must match #{RUNTIME_PATH} exactly or explicitly say 'see RUNTIME.md': " \
            "#{public_value.inspect} != #{runtime_value.inspect}."
end

if selected_profiles.include?("packaged-cli") && runtime
  if File.file?("CLI_INTERFACE.md")
    cli = File.read("CLI_INTERFACE.md")
    public_command = field_value.call(markdown_section.call(cli, "## Human CLI"), "Command")
    runtime_command = table_value.call(markdown_section.call(runtime, "### Packaged CLI commands"), "Human CLI")
    compare_commands.call("Packaged CLI command", public_command, runtime_command, RUNTIME_PATH)

    canonical_values = skill_lines.filter_map do |raw_line|
      normalized = raw_line.strip
      normalized = normalized[2..].strip if normalized.start_with?("- ")
      match = normalized.match(/\ACanonical command:\s*(.+?)\s*\z/)
      strip_backticks.call(match[1]) if match
    end

    if canonical_values.length != 1
      errors << "Selected profile 'packaged-cli' requires exactly one 'Canonical command:' summary in SKILL.md."
    else
      compare_commands.call("Packaged CLI command", public_command, canonical_values.first, SKILL_PATH)
    end

    launcher = markdown_section.call(cli, "## In-place agent launcher")
    if support_token.call(field_value.call(launcher, "Supported")) == "YES"
      public_launcher = field_value.call(launcher, "Command")
      runtime_launcher = table_value.call(markdown_section.call(runtime, "### Shared development commands"), "Agent launcher")
      compare_commands.call("In-place CLI launcher command", public_launcher, runtime_launcher, RUNTIME_PATH)
    end
  else
    errors << "Selected profile 'packaged-cli' requires CLI_INTERFACE.md for consistency validation."
  end
end

if selected_profiles.include?("mcp-enabled") && runtime
  unless File.file?("MCP_INTERFACE.md")
    errors << "Selected profile 'mcp-enabled' requires MCP_INTERFACE.md for consistency validation."
  else
    mcp = File.read("MCP_INTERFACE.md")
    runtime_commands = markdown_section.call(runtime, "### MCP commands")

    variant_specs = [
      {
        name: "stdio MCP server",
        public_heading: "## stdio MCP server variant",
        runtime_heading: "### stdio variant",
        command_pairs: [
          ["Launch command", "Start stdio MCP server"]
        ],
        selection_pairs: [
          ["Lifecycle owner", "Lifecycle owner"]
        ]
      },
      {
        name: "Streamable HTTP MCP server",
        public_heading: "## Streamable HTTP MCP server variant",
        runtime_heading: "### Streamable HTTP variant",
        command_pairs: [
          ["Start command", "Start Streamable HTTP MCP server"],
          ["Stop command or shutdown method", "Stop Streamable HTTP MCP server"],
          ["Health/readiness check", "Check MCP readiness"]
        ],
        selection_pairs: [
          ["Bind address", "Default bind address"],
          ["Port selection", "Port"],
          ["Supported protocol eras", "Supported protocol eras"],
          ["Revision-specific state model", "Revision-specific state model"],
          ["Authentication", "Authentication"]
        ]
      }
    ]

    variant_specs.each do |spec|
      public_section = markdown_section.call(mcp, spec[:public_heading])
      runtime_section = markdown_section.call(runtime, spec[:runtime_heading])
      public_support = support_token.call(field_value.call(public_section, "Supported"))
      runtime_support = support_token.call(table_value.call(runtime_section, "Supported"))

      unless %w[YES NO].include?(runtime_support)
        errors << "#{spec[:name]} requires a resolved YES/NO support declaration in #{RUNTIME_PATH}."
      end

      if %w[YES NO].include?(public_support) && %w[YES NO].include?(runtime_support) &&
         public_support != runtime_support
        errors << "#{spec[:name]} support must agree between MCP_INTERFACE.md and #{RUNTIME_PATH}."
      end

      next unless public_support == "YES"

      spec[:command_pairs].each do |public_label, runtime_purpose|
        compare_commands.call(
          "#{spec[:name]} #{public_label}",
          field_value.call(public_section, public_label),
          table_value.call(runtime_commands, runtime_purpose),
          RUNTIME_PATH
        )
      end

      spec[:selection_pairs].each do |public_label, runtime_item|
        compare_selections.call(
          "#{spec[:name]} #{public_label}",
          field_value.call(public_section, public_label),
          table_value.call(runtime_section, runtime_item)
        )
      end
    end

    public_client = markdown_section.call(mcp, "## Bundled ad hoc MCP tool client")
    runtime_client = markdown_section.call(runtime, "### Bundled ad hoc MCP tool client")
    public_client_support = support_token.call(field_value.call(public_client, "Supported"))
    runtime_client_support = support_token.call(table_value.call(runtime_client, "Supported"))

    unless %w[YES NO].include?(runtime_client_support)
      errors << "Bundled MCP client requires a resolved YES/NO support declaration in #{RUNTIME_PATH}."
    end

    if %w[YES NO].include?(public_client_support) &&
       %w[YES NO].include?(runtime_client_support) &&
       public_client_support != runtime_client_support
      errors << "Bundled MCP client support must agree between MCP_INTERFACE.md and #{RUNTIME_PATH}."
    end

    if public_client_support == "YES"
      compare_commands.call(
        "Bundled MCP client command",
        field_value.call(public_client, "Command"),
        table_value.call(runtime_client, "Bundled helper command"),
        RUNTIME_PATH
      )
      stable_public_command = table_value.call(runtime_client, "Stable public command")
      unless resolved_value.call(stable_public_command)
        errors << "Bundled MCP client Stable public command requires an explicit value in #{RUNTIME_PATH}."
      elsif concrete_value.call(stable_public_command) && !selected_profiles.include?("packaged-cli")
        errors << "Bundled MCP client Stable public command requires the 'packaged-cli' profile."
      end
      compare_selections.call(
        "Bundled MCP client transport",
        field_value.call(public_client, "Transport used"),
        table_value.call(runtime_client, "Supported transports")
      )
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Public interface and runtime contracts are consistent."
