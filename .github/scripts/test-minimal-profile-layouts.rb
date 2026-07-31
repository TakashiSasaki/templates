#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "find"
require "open3"
require "rbconfig"
require "tmpdir"

fixtures_root = File.expand_path("../fixtures/profiles", __dir__)
validator = File.expand_path("validate-skill-repository.rb", __dir__)

expected_files = {
  "instruction-only" => %w[SKILL.md],
  "knowledge-augmented" => %w[SKILL.md references/review-policy.md],
  "asset-driven" => %w[SKILL.md assets/response-template.txt],
  "script-assisted" => %w[SKILL.md scripts/normalize.rb]
}.freeze

failures = []

run_validator = lambda do |directory|
  Open3.capture3("git", "init", "--quiet", chdir: directory)
  Open3.capture3("git", "add", ".", chdir: directory)
  Open3.capture3(
    { "RUBYOPT" => nil },
    RbConfig.ruby,
    validator,
    chdir: directory
  )
end

copy_fixture = lambda do |name, directory|
  fixture = File.join(fixtures_root, name)
  FileUtils.cp_r("#{fixture}/.", directory)
end

expected_files.each do |name, expected|
  fixture = File.join(fixtures_root, name)
  actual = Find.find(fixture).filter_map do |path|
    next if path == fixture || File.directory?(path)

    path.delete_prefix("#{fixture}/")
  end.sort

  if actual != expected.sort
    failures << "#{name}: expected reduced layout #{expected.sort.inspect}, got #{actual.inspect}"
    next
  end

  Dir.mktmpdir("minimal-profile-#{name}") do |directory|
    copy_fixture.call(name, directory)
    _stdout, stderr, status = run_validator.call(directory)
    unless status.success?
      failures << "#{name}: expected the complete reduced repository to pass; diagnostics=#{stderr.strip.inspect}"
    end
  end
end

invalid_cases = [
  {
    name: "instruction-only rejects a retained runtime contract",
    fixture: "instruction-only",
    mutate: lambda do |directory|
      File.write(File.join(directory, "RUNTIME.md"), "# Unsupported runtime contract\n")
    end
  },
  {
    name: "knowledge-augmented rejects a missing declared reference",
    fixture: "knowledge-augmented",
    mutate: lambda do |directory|
      File.delete(File.join(directory, "references/review-policy.md"))
    end
  },
  {
    name: "asset-driven rejects an undeclared retained asset",
    fixture: "asset-driven",
    mutate: lambda do |directory|
      File.write(File.join(directory, "assets/undeclared.txt"), "undeclared\n")
    end
  },
  {
    name: "script-assisted rejects an undeclared retained helper",
    fixture: "script-assisted",
    mutate: lambda do |directory|
      File.write(File.join(directory, "scripts/undeclared.rb"), "puts 'undeclared'\n")
    end
  }
]

invalid_cases.each do |test_case|
  Dir.mktmpdir("invalid-minimal-profile") do |directory|
    copy_fixture.call(test_case.fetch(:fixture), directory)
    test_case.fetch(:mutate).call(directory)
    _stdout, stderr, status = run_validator.call(directory)
    if status.success?
      failures << "#{test_case.fetch(:name)}: expected validation failure"
    elsif stderr.strip.empty?
      failures << "#{test_case.fetch(:name)}: expected an actionable diagnostic"
    end
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Minimal profile repository layout tests passed."
