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

skill.declarations("Asset").each do |declaration|
  next if declaration.path == "assets/TODO"

  ["Use when", "Handling"].each do |field|
    unless ValuePolicy.concrete?(declaration.fields[field])
      errors << "SKILL.md asset declaration for #{declaration.path} must include a concrete '#{field}:' value."
    end
  end
end

unless selection.template_scaffold?
  executable_profiles = %w[script-assisted packaged-cli mcp-enabled browser-interface headless-service]
  general_directories = %w[src app lib bin server client tests]
  browser_directories = %w[web website frontend ui public static www]

  general_present = general_directories.any? { |directory| repository.operational_file_present?(directory) }
  browser_present = browser_directories.any? { |directory| repository.operational_file_present?(directory) }
  manifest_present = %w[
    package.json package-lock.json pnpm-lock.yaml yarn.lock bun.lock bun.lockb
    pyproject.toml requirements.txt uv.lock Pipfile Pipfile.lock Cargo.toml Cargo.lock
    go.mod go.sum Gemfile Gemfile.lock pom.xml build.gradle build.gradle.kts
    composer.json composer.lock
  ].any? { |path| repository.file?(path) }
  root_present = %w[
    index.html service-worker.js sw.js manifest.webmanifest Dockerfile compose.yml
    compose.yaml docker-compose.yml docker-compose.yaml
  ].any? { |path| repository.file?(path) }

  if (general_present || manifest_present || root_present) && (selected_profiles & executable_profiles).empty?
    errors << "Retained implementation or runtime signals require an executable or service profile."
  end

  if (browser_present || repository.file?("index.html") || repository.file?("manifest.webmanifest")) &&
     !selection.selected?("browser-interface")
    errors << "Retained browser implementation signals require selected profile 'browser-interface'."
  end
end

if selection.selected?("headless-service")
  runtime = repository.document("RUNTIME.md")
  if runtime
    service = runtime.section("## Headless service deployment")
    [
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
    ].each do |item|
      value = runtime.table_value(item, section: service)
      valid = item == "Supported" ? value == "YES" : ValuePolicy.concrete?(value)
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
