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

if selection.template_scaffold?
  scaffold_directories = %w[
    references assets scripts mcp src app lib bin server client tests
    web website frontend ui public static www
  ]
  customized = scaffold_directories.select { |directory| repository.operational_file_present?(directory) }
  manifests = %w[
    package.json package-lock.json pnpm-lock.yaml yarn.lock bun.lock bun.lockb
    pyproject.toml requirements.txt uv.lock Pipfile Pipfile.lock Cargo.toml Cargo.lock
    go.mod go.sum Gemfile Gemfile.lock pom.xml build.gradle build.gradle.kts
    composer.json composer.lock
  ].select { |path| repository.file?(path) }
  roots = %w[
    index.html service-worker.js sw.js manifest.webmanifest Dockerfile compose.yml
    compose.yaml docker-compose.yml docker-compose.yaml
  ].select { |path| repository.file?(path) }

  errors << "'template-scaffold' cannot be retained after adding implementation or operational files under: #{customized.join(', ')}." unless customized.empty?
  errors << "'template-scaffold' cannot be retained after adding runtime or package manifests: #{manifests.join(', ')}." unless manifests.empty?
  errors << "'template-scaffold' cannot be retained after adding root implementation or deployment files: #{roots.join(', ')}." unless roots.empty?
  unless skill.metadata["name"] == "agent-skill-template"
    errors << "'template-scaffold' is valid only while the skill name remains 'agent-skill-template'."
  end
end

skill.declarations("Script").each do |declaration|
  next if declaration.path == "scripts/TODO"

  required_fields = [
    "Run when",
    "Exact invocation",
    "Working directory",
    "Inputs and arguments",
    "Stdout/result",
    "Stderr/diagnostics",
    "Exit status",
    "Files or external state modified",
    "Network access",
    "Required permissions",
    "Automatic execution allowed",
    "Human confirmation required",
    "Idempotency and retry behavior"
  ]
  allow_none = [
    "Inputs and arguments",
    "Files or external state modified",
    "Network access",
    "Required permissions"
  ]

  required_fields.each do |field|
    value = declaration.fields[field]
    valid = allow_none.include?(field) ? ValuePolicy.resolved?(value) : ValuePolicy.concrete?(value)
    unless valid
      errors << "SKILL.md script declaration for #{declaration.path} must include a concrete '#{field}:' value."
    end
  end

  {
    "Automatic execution allowed" => declaration.fields["Automatic execution allowed"],
    "Human confirmation required" => declaration.fields["Human confirmation required"]
  }.each do |field, value|
    if ValuePolicy.resolved?(value) && !["YES", "NO", "WITH CONDITIONS"].include?(value.upcase)
      errors << "SKILL.md script declaration for #{declaration.path} must set '#{field}:' to YES, NO, or WITH CONDITIONS."
    end
  end
end

runtime_profiles = %w[script-assisted packaged-cli mcp-enabled browser-interface headless-service]
runtime = repository.document("RUNTIME.md")
if (selected_profiles & runtime_profiles).any? && runtime
  primary = runtime.section("## Primary implementation")
  ["Language", "Runtime", "Minimum runtime version", "Source layout", "Supported operating systems"].each do |item|
    unless ValuePolicy.concrete?(runtime.table_value(item, section: primary))
      errors << "Selected runtime-backed profiles require a concrete '#{item}' value in RUNTIME.md."
    end
  end
end

if selection.selected?("browser-interface")
  web = repository.document("WEB_INTERFACE.md")
  if web
    relationship = web.section("## Relationship to MCP")
    models = [
      "backend acts as an MCP client",
      "browser calls MCP directly",
      "UI uses a non-MCP application API",
      "mixed model"
    ].to_h { |label| [label, web.list_field(label, section: relationship)&.upcase] }

    unless models.values.all? { |value| %w[YES NO].include?(value) }
      errors << "WEB_INTERFACE.md must set every UI interaction model to YES or NO."
    end
    unless models.values.count("YES") == 1
      errors << "WEB_INTERFACE.md must select exactly one UI interaction model with YES."
    end
  end
end

if selection.selected?("mcp-enabled")
  mcp = repository.document("MCP_INTERFACE.md")
  runtime = repository.document("RUNTIME.md")
  if mcp
    variants = {
      "stdio" => {
        heading: "## stdio MCP server variant",
        runtime_heading: "### stdio variant",
        mandatory: ["Launch command", "Lifecycle owner"]
      },
      "Streamable HTTP" => {
        heading: "## Streamable HTTP MCP server variant",
        runtime_heading: "### Streamable HTTP variant",
        mandatory: [
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
        runtime_heading: "### Bundled ad hoc MCP tool client",
        mandatory: [
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

    supported_server_variants = []
    variants.each do |variant_name, spec|
      section = mcp.section(spec[:heading])
      if section.nil?
        errors << "Selected profile 'mcp-enabled' requires '#{spec[:heading]}' in MCP_INTERFACE.md."
        next
      end

      interface_support = ProfileContracts.support_token(mcp.field("Supported", section: section))
      unless %w[YES NO].include?(interface_support)
        errors << "MCP interface '#{variant_name}' must set 'Supported:' to YES or NO in MCP_INTERFACE.md."
        next
      end

      if runtime
        runtime_section = runtime.section(spec[:runtime_heading])
        runtime_support = ProfileContracts.support_token(runtime.table_value("Supported", section: runtime_section))
        unless %w[YES NO].include?(runtime_support)
          errors << "MCP variant '#{variant_name}' must set Supported to YES or NO in RUNTIME.md."
        end
        if %w[YES NO].include?(runtime_support) && interface_support != runtime_support
          errors << "MCP variant '#{variant_name}' has inconsistent Supported values between RUNTIME.md and MCP_INTERFACE.md."
        end
      end

      next unless interface_support == "YES"

      supported_server_variants << variant_name unless variant_name == "bundled MCP client"
      if /\b(?:TODO|UNSELECTED)\b/i.match?(section)
        errors << "Supported MCP interface '#{variant_name}' must not retain TODO or UNSELECTED fields in MCP_INTERFACE.md."
      end

      spec[:mandatory].each do |label|
        value = mcp.field(label, section: section)
        valid = if Array(spec[:allow_not_supported]).include?(label)
                  ValuePolicy.resolved?(value)
                else
                  ValuePolicy.concrete?(value)
                end
        unless valid
          errors << "Supported MCP interface '#{variant_name}' requires a concrete '#{label}:' value in MCP_INTERFACE.md."
        end
      end
    end

    if supported_server_variants.empty?
      errors << "Selected profile 'mcp-enabled' requires at least one supported MCP server variant in MCP_INTERFACE.md."
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Extended Agent Skill profile contracts are valid."
