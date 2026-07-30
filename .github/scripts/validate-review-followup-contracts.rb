#!/usr/bin/env ruby

require "find"
require "yaml"

skill_path = "SKILL.md"
unless File.file?(skill_path)
  warn "Missing universally required file: SKILL.md"
  exit 1
end

lines = File.readlines(skill_path, chomp: true)
text = lines.join("\n")

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

profile_values = lines.filter_map do |raw_line|
  line = normalize_line.call(raw_line)
  match = line.match(/\ASelected profiles:\s*(.+?)\s*\z/)
  strip_backticks.call(match[1]) if match
end

errors = []

if profile_values.length != 1
  errors << "SKILL.md must contain exactly one 'Selected profiles:' declaration."
else
  selected_profiles = profile_values.first.split(",").map(&:strip).reject(&:empty?)
  template_scaffold = selected_profiles == ["template-scaffold"]

  root_source_extensions = %w[
    .py .rb .js .mjs .cjs .jsx .ts .tsx .go .rs .java .kt .kts .cs .php
    .sh .bash .zsh .fish .ps1 .pl .lua .r .swift .scala .clj .ex .exs .erl
  ]
  root_implementation_files = Dir.children(".").select do |path|
    next false unless File.file?(path) && !File.symlink?(path)

    root_source_extensions.include?(File.extname(path).downcase)
  end

  if template_scaffold
    unless root_implementation_files.empty?
      errors << "'template-scaffold' cannot be retained after adding root-level implementation files: #{root_implementation_files.sort.join(', ')}."
    end
  else
    resource_profile_directories = {
      "knowledge-augmented" => "references",
      "asset-driven" => "assets",
      "script-assisted" => "scripts"
    }
    resource_profile_directories.each do |profile, directory|
      next unless selected_profiles.include?(profile)
      next if operational_file_present.call(directory)

      errors << "Selected profile '#{profile}' requires at least one operational file under #{directory}/."
    end

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

    parse_declarations.call("Reference").each do |declaration|
      next if declaration[:path] == "references/TODO.md"

      ["Read when", "Provides"].each do |field|
        unless concrete_value.call(declaration[:fields][field])
          errors << "SKILL.md reference declaration for #{declaration[:path]} must include a concrete '#{field}:' value."
        end
      end
    end

    if selected_profiles.include?("mcp-enabled")
      unless File.file?("RUNTIME.md")
        errors << "Selected profile 'mcp-enabled' requires RUNTIME.md."
      else
        runtime = File.read("RUNTIME.md")
        protocol = markdown_section.call(runtime, "## MCP protocol support")

        mandatory_protocol_items = [
          "Supported protocol revisions",
          "Supported protocol eras",
          "Default revision or negotiation mode",
          "MCP SDK or protocol library",
          "SDK version",
          "Legacy compatibility policy",
          "JSON Schema dialects",
          "Deprecated feature policy",
          "Negotiation and compatibility tests"
        ]

        mandatory_protocol_items.each do |item|
          unless concrete_value.call(table_value.call(protocol, item))
            errors << "Selected profile 'mcp-enabled' requires a concrete '#{item}' value in RUNTIME.md."
          end
        end

        unless resolved_value.call(table_value.call(protocol, "Optional MCP extensions"))
          errors << "Selected profile 'mcp-enabled' must resolve 'Optional MCP extensions' to a concrete list or NONE in RUNTIME.md."
        end
      end
    end

    if selected_profiles.include?("packaged-cli")
      unless operational_file_present.call("src")
        errors << "Selected profile 'packaged-cli' requires at least one non-guidance implementation file under src/."
      end
      unless operational_file_present.call("tests")
        errors << "Selected profile 'packaged-cli' requires at least one non-guidance test file under tests/."
      end

      unless File.file?("RUNTIME.md")
        errors << "Selected profile 'packaged-cli' requires RUNTIME.md."
      else
        runtime = File.read("RUNTIME.md")
        primary = markdown_section.call(runtime, "## Primary implementation")

        extract_path = lambda do |value|
          next nil unless concrete_value.call(value)

          quoted = value.scan(/`([^`]+)`/).flatten
          candidate = if quoted.length == 1
                        quoted.first
                      elsif quoted.empty? && value.match?(/\A[^\s]+\z/)
                        strip_backticks.call(value)
                      end
          next nil unless candidate
          next nil if candidate.start_with?("/") || candidate.split("/").include?("..")

          candidate
        end

        manifest_path = extract_path.call(table_value.call(primary, "Project manifest"))
        unless manifest_path && File.file?(manifest_path) && !File.symlink?(manifest_path)
          errors << "Selected profile 'packaged-cli' requires 'Project manifest' to name one retained regular file by exact relative path."
        end

        lockfile_value = table_value.call(primary, "Lockfile policy")
        lockfile_path = extract_path.call(lockfile_value)
        unless lockfile_path && File.file?(lockfile_path) && !File.symlink?(lockfile_path)
          errors << "Selected profile 'packaged-cli' requires 'Lockfile policy' to include one retained lockfile path, preferably in backticks."
        end

        if manifest_path && lockfile_path && manifest_path == lockfile_path
          errors << "Selected profile 'packaged-cli' must use distinct retained manifest and lockfile files."
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
