#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "lib/profile_contracts"

include ProfileContracts

begin
  skill = SkillDocument.read("SKILL.md")
  selection = ProfileSelection.load("SKILL.md", document: skill)
rescue ParseError => e
  warn e.message
  exit 1
end

repository = RepositorySnapshot.new
selected_profiles = selection.profiles
errors = []

source_extensions = %w[
  .py .pyw .rb .js .mjs .cjs .jsx .ts .tsx .go .rs .java .kt .kts .cs .fs .fsx
  .php .sh .bash .zsh .fish .ps1 .pl .pm .lua .r .swift .scala .clj .cljs .ex .exs
  .erl .hrl .c .h .cc .cpp .cxx .hpp .m .mm .dart .groovy .gradle .bats .feature .t
].freeze

root_implementation_files = repository.root_files.select do |path|
  source_extensions.include?(File.extname(path).downcase) || File.executable?(path)
end

if selection.template_scaffold?
  unless root_implementation_files.empty?
    errors << "'template-scaffold' cannot be retained after adding root-level implementation files: #{root_implementation_files.sort.join(', ')}."
  end
else
  [
    "## Purpose",
    "## Use this skill when",
    "## Workflow",
    "## Output requirements",
    "## Validation",
    "## Safety and approval"
  ].each do |heading|
    unless ValuePolicy.concrete?(skill.section(heading)&.strip)
      errors << "A concrete SKILL.md requires non-sentinel operational content under '#{heading}'."
    end
  end

  application_profiles = %w[packaged-cli mcp-enabled browser-interface headless-service]
  if !root_implementation_files.empty? && (selected_profiles & application_profiles).empty?
    errors << "Root-level implementation files require an application or service profile (packaged-cli, mcp-enabled, browser-interface, or headless-service): #{root_implementation_files.sort.join(', ')}."
  end

  {
    "knowledge-augmented" => "references",
    "asset-driven" => "assets",
    "script-assisted" => "scripts"
  }.each do |profile, directory|
    next unless selection.selected?(profile)
    next if repository.operational_file_present?(directory)

    errors << "Selected profile '#{profile}' requires at least one operational file under #{directory}/."
  end

  skill.declarations("Reference").each do |declaration|
    next if declaration.path == "references/TODO.md"

    ["Read when", "Provides"].each do |field|
      unless ValuePolicy.concrete?(declaration.fields[field])
        errors << "SKILL.md reference declaration for #{declaration.path} must include a concrete '#{field}:' value."
      end
    end
  end

  if selection.selected?("mcp-enabled")
    runtime = repository.document("RUNTIME.md")
    if runtime.nil?
      errors << "Selected profile 'mcp-enabled' requires RUNTIME.md."
    else
      protocol = runtime.section("## MCP protocol support")
      [
        "Supported protocol revisions",
        "Supported protocol eras",
        "Default revision or negotiation mode",
        "MCP SDK or protocol library",
        "SDK version",
        "Legacy compatibility policy",
        "JSON Schema dialects",
        "Deprecated feature policy",
        "Negotiation and compatibility tests"
      ].each do |item|
        unless ValuePolicy.concrete?(runtime.table_value(item, section: protocol))
          errors << "Selected profile 'mcp-enabled' requires a concrete '#{item}' value in RUNTIME.md."
        end
      end

      unless ValuePolicy.resolved?(runtime.table_value("Optional MCP extensions", section: protocol))
        errors << "Selected profile 'mcp-enabled' must resolve 'Optional MCP extensions' to a concrete list or NONE in RUNTIME.md."
      end

      http = runtime.section("### Streamable HTTP variant")
      if runtime.table_value("Supported", section: http) == "YES"
        [
          "Authentication",
          "Host-header validation",
          "Origin validation granularity",
          "Allowed origins and absent-Origin policy",
          "Connection-reuse security tests"
        ].each do |item|
          unless ValuePolicy.concrete?(runtime.table_value(item, section: http))
            errors << "Supported Streamable HTTP requires a concrete '#{item}' security decision in RUNTIME.md; absence sentinels are not allowed."
          end
        end
      end
    end
  end

  if selection.selected?("packaged-cli")
    unless repository.code_artifact_present?("src")
      errors << "Selected profile 'packaged-cli' requires at least one non-guidance regular source artifact under src/."
    end
    unless repository.code_artifact_present?("tests")
      errors << "Selected profile 'packaged-cli' requires at least one non-guidance regular test artifact under tests/."
    end

    runtime = repository.document("RUNTIME.md")
    if runtime.nil?
      errors << "Selected profile 'packaged-cli' requires RUNTIME.md."
    else
      primary = runtime.section("## Primary implementation")
      extract_path = lambda do |value|
        next nil unless ValuePolicy.concrete?(value)

        quoted = value.scan(/`([^`]+)`/).flatten
        candidate = if quoted.length == 1
                      quoted.first
                    elsif quoted.empty? && value.match?(/\A[^\s]+\z/)
                      ValuePolicy.strip_backticks(value)
                    end
        next nil unless candidate
        next nil if candidate.start_with?("/") || candidate.split("/").include?("..")

        candidate
      end

      manifest_path = extract_path.call(runtime.table_value("Project manifest", section: primary))
      unless manifest_path && repository.file?(manifest_path) && !repository.symlink?(manifest_path)
        errors << "Selected profile 'packaged-cli' requires 'Project manifest' to name one retained regular file by exact relative path."
      end

      lockfile_path = extract_path.call(runtime.table_value("Lockfile policy", section: primary))
      unless lockfile_path && repository.file?(lockfile_path) && !repository.symlink?(lockfile_path)
        errors << "Selected profile 'packaged-cli' requires 'Lockfile policy' to include one retained lockfile path, preferably in backticks."
      end

      if manifest_path && lockfile_path && manifest_path == lockfile_path
        errors << "Selected profile 'packaged-cli' must use distinct retained manifest and lockfile files."
      end

      cli = repository.document("CLI_INTERFACE.md")
      if cli
        commands = runtime.section("## Commands")
        runtime_command = runtime.table_value("Human CLI", section: commands)
        human_cli = cli.section("## Human CLI")
        interface_command = cli.field("Command", section: human_cli)

        if ValuePolicy.concrete?(runtime_command) && ValuePolicy.concrete?(interface_command) &&
           runtime_command != interface_command
          errors << "The packaged CLI command must match between RUNTIME.md ('#{runtime_command}') and CLI_INTERFACE.md ('#{interface_command}')."
        end
      end
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Review follow-up Agent Skill contracts are valid."
