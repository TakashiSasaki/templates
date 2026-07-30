#!/usr/bin/env ruby

require "find"
require "yaml"

skill_path = "SKILL.md"
lines = File.readlines(skill_path, chomp: true)

closing_index = (1...lines.length).find { |index| lines[index] == "---" }
frontmatter = lines[1...closing_index].join("\n")
metadata = YAML.safe_load(
  frontmatter,
  permitted_classes: [],
  permitted_symbols: [],
  aliases: false
)
name = metadata.fetch("name")

normalize_line = lambda do |line|
  normalized = line.strip
  normalized = normalized[2..].strip if normalized.start_with?("- ")
  normalized
end

strip_backticks = lambda do |value|
  normalized = value.strip
  if normalized.length >= 2 && normalized.start_with?("`") && normalized.end_with?("`")
    normalized[1...-1]
  else
    normalized
  end
end

profile_declarations = []

lines.each_with_index do |raw_line, index|
  line = normalize_line.call(raw_line)
  next unless (match = line.match(/\ASelected profiles:\s*(.+?)\s*\z/))

  profile_declarations << {
    value: strip_backticks.call(match[1]),
    line: index + 1
  }
end

if profile_declarations.length != 1
  warn "SKILL.md must contain exactly one 'Selected profiles:' declaration."
  exit 1
end

selected_profiles = profile_declarations.first[:value].split(",").map(&:strip).reject(&:empty?)
allowed_profiles = %w[
  instruction-only
  knowledge-augmented
  asset-driven
  script-assisted
  packaged-cli
  mcp-enabled
  browser-interface
  headless-service
]

if selected_profiles == ["template-scaffold"]
  unless name == "agent-skill-template"
    warn "'template-scaffold' is valid only for the uncustomized agent-skill-template."
    exit 1
  end
  exit 0
end

if selected_profiles.include?("template-scaffold")
  warn "'template-scaffold' cannot be combined with concrete skill profiles."
  exit 1
end

if selected_profiles.empty?
  warn "SKILL.md must select at least one concrete profile."
  exit 1
end

duplicates = selected_profiles.group_by(&:itself).select { |_profile, values| values.length > 1 }.keys
unless duplicates.empty?
  warn "SKILL.md contains duplicate selected profiles: #{duplicates.join(', ')}"
  exit 1
end

invalid_profiles = selected_profiles - allowed_profiles
unless invalid_profiles.empty?
  warn "SKILL.md contains unknown selected profiles: #{invalid_profiles.join(', ')}"
  exit 1
end

profile_requirements = {
  "packaged-cli" => ["RUNTIME.md", "INTERFACES.md"],
  "mcp-enabled" => ["RUNTIME.md", "INTERFACES.md", "docs/mcp-transports.md"],
  "browser-interface" => ["RUNTIME.md", "WEB_INTERFACE.md"]
}

resource_profile_requirements = {
  "references" => "knowledge-augmented",
  "assets" => "asset-driven",
  "scripts" => "script-assisted"
}

operational_files_present = lambda do |directory|
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

errors = []

selected_profiles.each do |profile|
  profile_requirements.fetch(profile, []).each do |required_path|
    unless File.file?(required_path)
      errors << "Selected profile '#{profile}' requires contract file: #{required_path}"
    end
  end
end

resource_profile_requirements.each do |directory, required_profile|
  next unless operational_files_present.call(directory)
  next if selected_profiles.include?(required_profile)

  errors << "Retained operational files under #{directory}/ require selected profile '#{required_profile}'."
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end
