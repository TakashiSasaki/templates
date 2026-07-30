#!/usr/bin/env ruby

require "find"
require "yaml"

skill_path = "SKILL.md"
unless File.file?(skill_path)
  warn "Missing universally required file: SKILL.md"
  exit 1
end

lines = File.readlines(skill_path, chomp: true)
unless lines.first == "---"
  warn "SKILL.md must begin with YAML frontmatter."
  exit 1
end

closing_index = (1...lines.length).find { |index| lines[index] == "---" }
unless closing_index
  warn "SKILL.md YAML frontmatter must have a closing --- delimiter."
  exit 1
end

YAML.safe_load(
  lines[1...closing_index].join("\n"),
  permitted_classes: [],
  permitted_symbols: [],
  aliases: false
)

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

table_value = lambda do |text, item|
  match = text&.match(/^\|\s*#{Regexp.escape(item)}\s*\|\s*(.*?)\s*\|\s*$/)
  match && strip_backticks.call(match[1])
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

  parse_declarations = lambda do |label|
    declarations = []
    current = nil

    lines.each_with_index do |raw_line, index|
      line = normalize_line.call(raw_line)

      if (match = line.match(/\A#{Regexp.escape(label)}:\s*(.+?)\s*\z/))
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

    declarations
  end

  parse_declarations.call("Asset").each do |declaration|
    next if declaration[:path] == "assets/TODO"

    ["Use when", "Handling"].each do |field|
      unless concrete_value.call(declaration[:fields][field])
        errors << "SKILL.md asset declaration for #{declaration[:path]} must include a concrete '#{field}:' value."
      end
    end
  end

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

  unless template_scaffold
    executable_profiles = %w[
      script-assisted
      packaged-cli
      mcp-enabled
      browser-interface
      headless-service
    ]

    general_implementation_directories = %w[
      src
      app
      lib
      bin
      server
      client
      tests
    ]
    browser_implementation_directories = %w[
      web
      website
      frontend
      ui
      public
      static
      www
    ]

    general_implementation_present = general_implementation_directories.any? do |directory|
      operational_file_present.call(directory)
    end
    browser_implementation_present = browser_implementation_directories.any? do |directory|
      operational_file_present.call(directory)
    end

    manifest_present = %w[
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
    ].any? { |path| File.file?(path) }

    root_implementation_present = %w[
      index.html
      service-worker.js
      sw.js
      manifest.webmanifest
      Dockerfile
      compose.yml
      compose.yaml
      docker-compose.yml
      docker-compose.yaml
    ].any? { |path| File.file?(path) }

    if (general_implementation_present || manifest_present || root_implementation_present) &&
       (selected_profiles & executable_profiles).empty?
      errors << "Retained implementation or runtime signals require an executable or service profile."
    end

    if (browser_implementation_present || File.file?("index.html") || File.file?("manifest.webmanifest")) &&
       !selected_profiles.include?("browser-interface")
      errors << "Retained browser implementation signals require selected profile 'browser-interface'."
    end
  end

  if selected_profiles.include?("headless-service") && File.file?("RUNTIME.md")
    runtime = File.read("RUNTIME.md")
    service = markdown_section.call(runtime, "## Headless service deployment")
    mandatory_service_items = [
      "Supported",
      "Service runtime or entry point",
      "Protocol or API surface",
      "Endpoint or listener model",
      "Default bind address",
      "Port policy",
      "Authentication",
      "Authorization",
      "Exposure and non-loopback policy",
      "Request size and rate limits",
      "Concurrent request policy",
      "State or session model",
      "Readiness check",
      "Liveness check",
      "Timeout and cancellation policy",
      "Graceful shutdown and restart policy",
      "Deployment topology",
      "Security and deployment smoke tests"
    ]

    mandatory_service_items.each do |item|
      value = table_value.call(service, item)
      valid = item == "Supported" ? value == "YES" : concrete_value.call(value)
      unless valid
        errors << "Selected profile 'headless-service' requires a concrete '#{item}' value in RUNTIME.md."
      end
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "Concrete Agent Skill profile consistency is valid."
