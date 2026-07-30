#!/usr/bin/env ruby

require "find"
require "yaml"

SKILL_PATH = "SKILL.md"

unless File.file?(SKILL_PATH)
  warn "Missing universally required file: SKILL.md"
  exit 1
end

lines = File.readlines(SKILL_PATH, chomp: true)
skill_text = lines.join("\n")

unless lines.first == "---"
  warn "SKILL.md must begin with YAML frontmatter."
  exit 1
end

closing_index = (1...lines.length).find { |index| lines[index] == "---" }
unless closing_index
  warn "SKILL.md YAML frontmatter must have a closing --- delimiter."
  exit 1
end

metadata = YAML.safe_load(
  lines[1...closing_index].join("\n"),
  permitted_classes: [],
  permitted_symbols: [],
  aliases: false
)

unless metadata.is_a?(Hash)
  warn "SKILL.md YAML frontmatter must be a mapping."
  exit 1
end

name = metadata["name"]

normalize_line = lambda do |line|
  normalized = line.strip
  normalized = normalized[2..].strip if normalized.start_with?("- ")
  normalized
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

markdown_section = lambda do |text, heading|
  level = heading[/\A#+/].length
  boundary = level == 2 ? "^##\\s|\\z" : "^(?:##|###)\\s|\\z"
  pattern = Regexp.new(
    "^#{Regexp.escape(heading)}\\s*$\\n(.*?)(?=#{boundary})",
    Regexp::MULTILINE
  )
  match = text.match(pattern)
  match && match[1]
end

field_value = lambda do |text, label|
  match = text&.match(/^#{Regexp.escape(label)}:\s*(.*?)\s*$/)
  match && strip_backticks.call(match[1])
end

list_field_value = lambda do |text, label|
  match = text&.match(/^\s*-\s*#{Regexp.escape(label)}:\s*(.*?)\s*$/)
  match && strip_backticks.call(match[1])
end

table_value = lambda do |text, item|
  match = text&.match(/^\|\s*#{Regexp.escape(item)}\s*\|\s*(.*?)\s*\|\s*$/)
  match && strip_backticks.call(match[1])
end

support_token = lambda do |value|
  value&.strip&.split(/[;\s]/)&.first&.upcase
end

profile_lines = lines.filter_map do |raw_line|
  line = normalize_line.call(raw_line)
  match = line.match(/\ASelected profiles:\s*(.+?)\s*\z/)
  strip_backticks.call(match[1]) if match
end

errors = []

if profile_lines.length != 1
  errors << "SKILL.md must contain exactly one 'Selected profiles:' declaration."
else
  selected_profiles = profile_lines.first.split(",").map(&:strip).reject(&:empty?)
  template_scaffold = selected_profiles == ["template-scaffold"]

  operational_file_present = lambda do |directory|
    next false unless Dir.exist?(directory) && !File.symlink?(directory)

    found = false
    Find.find(directory) do |path|
      next if path == directory
      next if File.directory?(path)
      next if path == "#{directory}/README.md"

      found = true
      break
    end
    found
  end

  if template_scaffold
    scaffold_customization_directories = %w[
      references
      assets
      scripts
      mcp
      src
      app
      lib
      bin
      server
      client
      tests
      web
      website
      frontend
      ui
      public
      static
      www
    ]

    customized_directories = scaffold_customization_directories.select do |directory|
      operational_file_present.call(directory)
    end

    manifest_signals = %w[
      package.json
      package-lock.json
      pnpm-lock.yaml
      yarn.lock
      bun.lock
      bun.lockb
      pyproject.toml
      requirements.txt
      uv.lock
      Pipfile
      Pipfile.lock
      Cargo.toml
      Cargo.lock
      go.mod
      go.sum
      Gemfile
      Gemfile.lock
      pom.xml
      build.gradle
      build.gradle.kts
      composer.json
      composer.lock
    ].select { |path| File.file?(path) }

    root_implementation_signals = %w[
      index.html
      service-worker.js
      sw.js
      manifest.webmanifest
      Dockerfile
      compose.yml
      compose.yaml
      docker-compose.yml
      docker-compose.yaml
    ].select { |path| File.file?(path) }

    unless customized_directories.empty?
      errors << "'template-scaffold' cannot be retained after adding implementation or operational files under: #{customized_directories.join(', ')}."
    end
    unless manifest_signals.empty?
      errors << "'template-scaffold' cannot be retained after adding runtime or package manifests: #{manifest_signals.join(', ')}."
    end
    unless root_implementation_signals.empty?
      errors << "'template-scaffold' cannot be retained after adding root implementation or deployment files: #{root_implementation_signals.join(', ')}."
    end
    unless name == "agent-skill-template"
      errors << "'template-scaffold' is valid only while the skill name remains 'agent-skill-template'."
    end
  end

  declarations = []
  current = nil

  lines.each_with_index do |raw_line, index|
    line = normalize_line.call(raw_line)

    if (match = line.match(/\AScript:\s*(.+?)\s*\z/))
      current = {
        path: strip_backticks.call(match[1]),
        line: index + 1,
        fields: {}
      }
      declarations << current
      next
    end

    next unless current

    if line.start_with?("#") || line == "```"
      current = nil
      next
    end

    if (match = line.match(/\A([^:]+):\s*(.*?)\s*\z/))
      current[:fields][match[1].strip] = strip_backticks.call(match[2])
    end
  end

  required_script_fields = [
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

  script_fields_allowing_plain_none = [
    "Inputs and arguments",
    "Files or external state modified",
    "Network access",
    "Required permissions"
  ]

  declarations.each do |declaration|
    next if declaration[:path] == "scripts/TODO"

    required_script_fields.each do |field|
      value = declaration[:fields][field]
      valid = if script_fields_allowing_plain_none.include?(field)
        resolved_value.call(value)
      else
        concrete_value.call(value)
      end
      unless valid
        errors << "SKILL.md script declaration for #{declaration[:path]} must include a concrete '#{field}:' value."
      end
    end

    automatic = declaration[:fields]["Automatic execution allowed"]
    if resolved_value.call(automatic) && !["YES", "NO", "WITH CONDITIONS"].include?(automatic.upcase)
      errors << "SKILL.md script declaration for #{declaration[:path]} must set 'Automatic execution allowed:' to YES, NO, or WITH CONDITIONS."
    end

    confirmation = declaration[:fields]["Human confirmation required"]
    if resolved_value.call(confirmation) && !["YES", "NO", "WITH CONDITIONS"].include?(confirmation.upcase)
      errors << "SKILL.md script declaration for #{declaration[:path]} must set 'Human confirmation required:' to YES, NO, or WITH CONDITIONS."
    end
  end

  runtime_profiles = %w[
    script-assisted
    packaged-cli
    mcp-enabled
    browser-interface
    headless-service
  ]
  if (selected_profiles & runtime_profiles).any? && File.file?("RUNTIME.md")
    runtime = File.read("RUNTIME.md")
    primary = markdown_section.call(runtime, "## Primary implementation")
    [
      "Language",
      "Runtime",
      "Minimum runtime version",
      "Source layout",
      "Supported operating systems"
    ].each do |item|
      unless concrete_value.call(table_value.call(primary, item))
        errors << "Selected runtime-backed profiles require a concrete '#{item}' value in RUNTIME.md."
      end
    end
  end

  if selected_profiles.include?("browser-interface") && File.file?("WEB_INTERFACE.md")
    web_interface = File.read("WEB_INTERFACE.md")
    relationship = markdown_section.call(web_interface, "## Relationship to MCP")
    models = [
      "backend acts as an MCP client",
      "browser calls MCP directly",
      "UI uses a non-MCP application API",
      "mixed model"
    ].to_h do |label|
      [label, list_field_value.call(relationship, label)&.upcase]
    end

    invalid_models = models.select { |_label, value| !%w[YES NO].include?(value) }
    unless invalid_models.empty?
      errors << "WEB_INTERFACE.md must set every UI interaction model to YES or NO."
    end
    unless models.values.count("YES") == 1
      errors << "WEB_INTERFACE.md must select exactly one UI interaction model with YES."
    end
  end

  if selected_profiles.include?("mcp-enabled") && File.file?("INTERFACES.md")
    interfaces = File.read("INTERFACES.md")

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

    runtime = File.file?("RUNTIME.md") ? File.read("RUNTIME.md") : nil
    supported_server_variants = []

    variants.each do |variant_name, spec|
      section = markdown_section.call(interfaces, spec[:heading])
      if section.nil?
        errors << "Selected profile 'mcp-enabled' requires '#{spec[:heading]}' in INTERFACES.md."
        next
      end

      interface_support = support_token.call(field_value.call(section, "Supported"))
      unless %w[YES NO].include?(interface_support)
        errors << "MCP interface '#{variant_name}' must set 'Supported:' to YES or NO in INTERFACES.md."
        next
      end

      if runtime
        runtime_section = markdown_section.call(runtime, spec[:runtime_heading])
        runtime_support = support_token.call(table_value.call(runtime_section, "Supported"))
        unless %w[YES NO].include?(runtime_support)
          errors << "MCP variant '#{variant_name}' must set Supported to YES or NO in RUNTIME.md."
        end
        if %w[YES NO].include?(runtime_support) && interface_support != runtime_support
          errors << "MCP variant '#{variant_name}' has inconsistent Supported values between RUNTIME.md and INTERFACES.md."
        end
      end

      next unless interface_support == "YES"

      supported_server_variants << variant_name unless variant_name == "bundled MCP client"

      if /\b(?:TODO|UNSELECTED)\b/i.match?(section)
        errors << "Supported MCP interface '#{variant_name}' must not retain TODO or UNSELECTED fields in INTERFACES.md."
      end

      spec[:mandatory].each do |label|
        value = field_value.call(section, label)
        allow_not_supported = Array(spec[:allow_not_supported]).include?(label)
        valid = allow_not_supported ? resolved_value.call(value) : concrete_value.call(value)
        unless valid
          errors << "Supported MCP interface '#{variant_name}' requires a concrete '#{label}:' value in INTERFACES.md."
        end
      end
    end

    if supported_server_variants.empty?
      errors << "Selected profile 'mcp-enabled' requires at least one supported MCP server variant in INTERFACES.md."
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Extended Agent Skill profile contracts are valid."
