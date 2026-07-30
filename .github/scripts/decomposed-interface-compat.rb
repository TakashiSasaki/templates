# frozen_string_literal: true

# Transitional validation adapter for the Phase 2 interface split.
#
# Existing validators still parse the former monolithic INTERFACES.md shape.
# Until the validator consolidation phase replaces those parsers, this adapter:
#
# 1. enforces profile-aware retention and completeness of CLI_INTERFACE.md and
#    MCP_INTERFACE.md;
# 2. presents INTERFACES.md plus the selected profile-specific documents as one
#    logical read-only document to the legacy validators.
#
# The repository documents themselves remain decomposed and have one source of
# truth. Remove this adapter when the validators consume the contract model
# directly.

unless defined?(DECOMPOSED_INTERFACE_COMPAT_LOADED)
  DECOMPOSED_INTERFACE_COMPAT_LOADED = true

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

  errors = []
  skill_path = "SKILL.md"
  selected_profiles = []
  template_scaffold = false

  if File.file?(skill_path)
    lines = File.readlines(skill_path, chomp: true)
    profile_values = lines.filter_map do |raw_line|
      normalized = raw_line.strip
      normalized = normalized[2..].strip if normalized.start_with?("- ")
      match = normalized.match(/\ASelected profiles:\s*(.+?)\s*\z/)
      strip_backticks.call(match[1]) if match
    end

    if profile_values.length == 1
      selected_profiles = profile_values.first.split(",").map(&:strip).reject(&:empty?)
      template_scaffold = selected_profiles == ["template-scaffold"]
    end
  end

  unless template_scaffold
    required_contracts = {
      "packaged-cli" => "CLI_INTERFACE.md",
      "mcp-enabled" => "MCP_INTERFACE.md"
    }
    required_contracts.each do |profile, path|
      if selected_profiles.include?(profile) && !File.file?(path)
        errors << "Selected profile '#{profile}' requires contract file: #{path}"
      end
    end

    supported_contracts = {
      "CLI_INTERFACE.md" => ["packaged-cli"],
      "MCP_INTERFACE.md" => ["mcp-enabled"]
    }
    supported_contracts.each do |path, profiles|
      next unless File.exist?(path)
      next unless (selected_profiles & profiles).empty?

      errors << "Retained contract #{path} is unsupported by the selected profiles."
    end

    validate_common_contract = lambda do |path, required_headings|
      next nil unless File.file?(path)

      document = File.read(path)
      status = field_value.call(document, "Selection status")
      unless status == "SELECTED"
        errors << "Selected contract #{path} requires 'Selection status: SELECTED'."
      end

      if /\b(?:TODO|UNSELECTED)\b/i.match?(document)
        errors << "Selected contract #{path} must not retain TODO or UNSELECTED placeholders."
      end

      required_headings.each do |heading|
        section = markdown_section.call(document, heading)
        if section.nil? || section.strip.empty?
          errors << "Selected contract #{path} requires non-empty section '#{heading}'."
        end
      end

      document
    end

    if selected_profiles.include?("packaged-cli")
      cli = validate_common_contract.call(
        "CLI_INTERFACE.md",
        [
          "## Status",
          "## Human CLI",
          "## In-place agent launcher",
          "## Inputs, outputs, and side effects",
          "## Compatibility and versioning",
          "## Semantic-equivalence and test requirements",
          "## Decision rationale"
        ]
      )

      if cli
        human_cli = markdown_section.call(cli, "## Human CLI")
        ["Command", "Working directory", "Format", "Contract version field"].each do |label|
          unless concrete_value.call(field_value.call(human_cli, label))
            errors << "Selected contract CLI_INTERFACE.md requires a concrete '#{label}:' value."
          end
        end

        launcher = markdown_section.call(cli, "## In-place agent launcher")
        launcher_support = support_token.call(field_value.call(launcher, "Supported"))
        unless %w[YES NO].include?(launcher_support)
          errors << "CLI_INTERFACE.md must set the in-place launcher 'Supported:' value to YES or NO."
        end
        ["Command", "Delegates to"].each do |label|
          value = field_value.call(launcher, label)
          valid = launcher_support == "YES" ? concrete_value.call(value) : resolved_value.call(value)
          unless valid
            errors << "CLI_INTERFACE.md requires a resolved '#{label}:' value for the selected launcher support state."
          end
        end

        io_contract = markdown_section.call(cli, "## Inputs, outputs, and side effects")
        absence_allowed = ["Files or external state modified", "Network access", "Required permissions"]
        [
          "Input forms and precedence",
          "Standard output",
          "Standard error",
          "Files or external state modified",
          "Network access",
          "Required permissions",
          "Confirmation policy",
          "Timeout and cancellation",
          "Idempotency and retry behavior"
        ].each do |item|
          value = table_value.call(io_contract, item)
          valid = absence_allowed.include?(item) ? resolved_value.call(value) : concrete_value.call(value)
          unless valid
            errors << "CLI_INTERFACE.md requires a resolved '#{item}' behavior."
          end
        end

        compatibility = markdown_section.call(cli, "## Compatibility and versioning")
        ["Compatibility policy", "Deprecation policy", "Structured contract version source"].each do |label|
          unless concrete_value.call(field_value.call(compatibility, label))
            errors << "CLI_INTERFACE.md requires a concrete '#{label}:' value."
          end
        end

        rationale = markdown_section.call(cli, "## Decision rationale")
        unless concrete_value.call(field_value.call(rationale, "Rationale"))
          errors << "CLI_INTERFACE.md requires a concrete 'Rationale:' value."
        end
      end
    end

    if selected_profiles.include?("mcp-enabled")
      mcp = validate_common_contract.call(
        "MCP_INTERFACE.md",
        [
          "## Status",
          "## MCP protocol reference",
          "## stdio MCP server variant",
          "## Streamable HTTP MCP server variant",
          "## Bundled ad hoc MCP tool client",
          "## Semantic-equivalence and test requirements",
          "## Decision rationale"
        ]
      )

      if mcp
        protocol = markdown_section.call(mcp, "## MCP protocol reference")
        ["Public negotiation and fallback behavior", "Public compatibility statement"].each do |label|
          unless concrete_value.call(field_value.call(protocol, label))
            errors << "MCP_INTERFACE.md requires a concrete '#{label}:' value."
          end
        end

        variants = {
          "stdio" => {
            heading: "## stdio MCP server variant",
            fields: ["Launch command", "Lifecycle owner"]
          },
          "Streamable HTTP" => {
            heading: "## Streamable HTTP MCP server variant",
            fields: [
              "Start command",
              "Stop command or shutdown method",
              "Endpoint URL",
              "Bind address",
              "Port selection",
              "Supported protocol eras",
              "Revision-specific state model",
              "Authentication",
              "Health/readiness check"
            ]
          },
          "bundled MCP client" => {
            heading: "## Bundled ad hoc MCP tool client",
            fields: [
              "Scope",
              "Command",
              "Transport used",
              "Negotiation and compatibility behavior",
              "Invocation scope",
              "Interaction modes",
              "Task or extension support"
            ],
            allow_not_supported: ["Task or extension support"]
          }
        }

        support_values = {}
        variants.each do |variant, specification|
          section = markdown_section.call(mcp, specification[:heading])
          support = support_token.call(field_value.call(section, "Supported"))
          support_values[variant] = support
          unless %w[YES NO].include?(support)
            errors << "MCP_INTERFACE.md must set '#{variant}' Supported to YES or NO."
          end

          specification[:fields].each do |label|
            value = field_value.call(section, label)
            allow_not_supported = Array(specification[:allow_not_supported]).include?(label)
            valid = if support == "YES"
                      allow_not_supported ? resolved_value.call(value) : concrete_value.call(value)
                    else
                      resolved_value.call(value)
                    end
            unless valid
              errors << "MCP_INTERFACE.md requires a resolved '#{label}:' value for '#{variant}'."
            end
          end
        end

        unless support_values.values_at("stdio", "Streamable HTTP").include?("YES")
          errors << "Selected profile 'mcp-enabled' requires at least one supported MCP server variant in MCP_INTERFACE.md."
        end

        rationale = markdown_section.call(mcp, "## Decision rationale")
        unless concrete_value.call(field_value.call(rationale, "Rationale"))
          errors << "MCP_INTERFACE.md requires a concrete 'Rationale:' value."
        end
      end
    end
  end

  unless errors.empty?
    errors.uniq.each { |error| warn error }
    exit 1
  end

  class << File
    alias_method :read_before_decomposed_interface_compat, :read

    def read(path, *args, **kwargs)
      content = read_before_decomposed_interface_compat(path, *args, **kwargs)
      return content unless path.to_s == "INTERFACES.md"

      additions = %w[CLI_INTERFACE.md MCP_INTERFACE.md].filter_map do |contract_path|
        next unless file?(contract_path)

        read_before_decomposed_interface_compat(contract_path, *args, **kwargs)
      end

      ([content] + additions).join("\n\n")
    end
  end
end
