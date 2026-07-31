#!/usr/bin/env ruby
# frozen_string_literal: true

require "find"
require "pathname"
require "rbconfig"
require_relative "lib/profile_contracts"

include ProfileContracts

begin
  skill = SkillDocument.read("SKILL.md")
  ProfileSelection.load("SKILL.md", document: skill)
rescue ParseError => e
  warn e.message
  exit 1
end

errors = []
name = skill.metadata["name"]
unless name.is_a?(String) && name.length.between?(1, 64) && /\A[a-z0-9]+(?:-[a-z0-9]+)*\z/.match?(name)
  errors << "SKILL.md frontmatter name must be a 1-64 character lowercase hyphenated string."
end

description = skill.metadata["description"]
unless description.is_a?(String) && !description.strip.empty?
  errors << "SKILL.md frontmatter description must be a non-empty string."
end

resource_specs = {
  "Reference" => {
    directory: "references",
    placeholder: "references/TODO.md",
    required_fields: ["Read when", "Provides"]
  },
  "Asset" => {
    directory: "assets",
    placeholder: "assets/TODO",
    required_fields: ["Use when", "Handling"]
  },
  "Script" => {
    directory: "scripts",
    placeholder: "scripts/TODO",
    required_fields: ["Run when", "Exact invocation"]
  }
}.freeze

declarations_by_path = {}
resource_specs.each do |label, spec|
  skill.declarations(label).each do |declaration|
    path = declaration.path
    next if path == spec.fetch(:placeholder)

    pathname = Pathname.new(path)
    clean_path = pathname.cleanpath.to_s
    expected_prefix = "#{spec.fetch(:directory)}/"

    if pathname.absolute? || clean_path != path || !path.start_with?(expected_prefix)
      errors << "SKILL.md line #{declaration.line_number} has an invalid #{label} path: #{path}"
      next
    end

    if declarations_by_path.key?(path)
      errors << "SKILL.md declares the same operational resource more than once: #{path}"
      next
    end

    declarations_by_path[path] = declaration

    spec.fetch(:required_fields).each do |field|
      value = declaration.fields[field]
      unless ValuePolicy.resolved?(value)
        errors << "SKILL.md declaration for #{path} must include a concrete '#{field}:' value."
      end
    end

    unless File.file?(path) && !File.symlink?(path)
      errors << "SKILL.md declares a missing or non-regular operational resource: #{path}"
    end
  end
end

resource_specs.each do |_label, spec|
  directory = spec.fetch(:directory)
  if File.symlink?(directory)
    errors << "Operational resource directory symlinks are not allowed: #{directory}"
    next
  end
  next unless Dir.exist?(directory)

  Find.find(directory) do |path|
    next if path == directory

    if File.symlink?(path)
      errors << "Operational resource symlinks are not allowed: #{path}"
      Find.prune if File.directory?(path)
      next
    end

    next if File.directory?(path)
    next if path == "#{directory}/README.md"

    unless File.file?(path)
      errors << "Operational resources must be regular files: #{path}"
      next
    end

    unless declarations_by_path.key?(path)
      label = resource_specs.find do |_candidate_label, candidate_spec|
        path.start_with?("#{candidate_spec.fetch(:directory)}/")
      end&.first
      errors << "SKILL.md must declare the exact retained resource path as '#{label}: #{path}'."
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

profile_validator = File.expand_path("validate-profile-contracts.rb", __dir__)
success = system({ "RUBYOPT" => nil }, RbConfig.ruby, profile_validator)
exit($?.exitstatus || 1) unless success

puts "Agent Skill repository structure and profile contracts are valid."
