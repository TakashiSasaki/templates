# frozen_string_literal: true

# Transitional validation adapter for the Phase 2 interface split.
#
# Existing validators still parse the former monolithic INTERFACES.md shape.
# Until the validator consolidation phase replaces those parsers, this adapter:
#
# 1. enforces profile-aware retention of CLI_INTERFACE.md and MCP_INTERFACE.md;
# 2. presents INTERFACES.md plus the selected profile-specific documents as one
#    logical read-only document to the legacy validators.
#
# The repository documents themselves remain decomposed and have one source of
# truth. Remove this adapter when the validators consume the contract model
# directly.

require "yaml"

unless defined?(DECOMPOSED_INTERFACE_COMPAT_LOADED)
  DECOMPOSED_INTERFACE_COMPAT_LOADED = true

  skill_path = "SKILL.md"
  if File.file?(skill_path)
    lines = File.readlines(skill_path, chomp: true)
    profile_values = lines.filter_map do |raw_line|
      normalized = raw_line.strip
      normalized = normalized[2..].strip if normalized.start_with?("- ")
      match = normalized.match(/\ASelected profiles:\s*(.+?)\s*\z/)
      next unless match

      value = match[1].strip
      value = value[1...-1] if value.length >= 2 && value.start_with?("`") && value.end_with?("`")
      value
    end

    errors = []
    if profile_values.length == 1
      selected_profiles = profile_values.first.split(",").map(&:strip).reject(&:empty?)
      template_scaffold = selected_profiles == ["template-scaffold"]

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
      end
    end

    unless errors.empty?
      errors.uniq.each { |error| warn error }
      exit 1
    end
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
