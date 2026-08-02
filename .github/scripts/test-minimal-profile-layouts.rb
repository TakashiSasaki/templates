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
  "script-assisted" => %w[SKILL.md scripts/normalize.rb],
  "combined-resources" => %w[
    SKILL.md
    assets/response-template.txt
    references/review-policy.md
    scripts/normalize.rb
  ]
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

replace_selected_profiles = lambda do |directory, replacement|
  path = File.join(directory, "SKILL.md")
  original = "Selected profiles: knowledge-augmented, asset-driven, script-assisted"
  content = File.read(path)
  replaced = content.sub(original, "Selected profiles: #{replacement}")
  raise "combined fixture selected-profile line was not found" if replaced == content

  File.write(path, replaced)
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

%w[script-assisted combined-resources].each do |fixture_name|
  Dir.mktmpdir("#{fixture_name}-execution") do |directory|
    copy_fixture.call(fixture_name, directory)
    File.binwrite(File.join(directory, "input.txt"), "alpha  \r\nbeta\t\r\n")
    stdout, stderr, status = Open3.capture3(
      RbConfig.ruby,
      "scripts/normalize.rb",
      "input.txt",
      "output.txt",
      chdir: directory
    )
    output = File.binread(File.join(directory, "output.txt")) if File.file?(File.join(directory, "output.txt"))
    unless status.success? && stderr.empty? && stdout == "output.txt\n" && output == "alpha\nbeta\n"
      failures << "#{fixture_name} helper: expected deterministic normalization; " \
                  "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, " \
                  "stderr=#{stderr.inspect}, output=#{output.inspect}"
    end

    File.binwrite(File.join(directory, "invalid.txt"), [0xFF].pack("C"))
    stdout, stderr, status = Open3.capture3(
      RbConfig.ruby,
      "scripts/normalize.rb",
      "invalid.txt",
      "invalid-output.txt",
      chdir: directory
    )
    unless status.exitstatus == 3 && stdout.empty? && stderr == "invalid UTF-8 input\n" &&
           !File.exist?(File.join(directory, "invalid-output.txt"))
      failures << "#{fixture_name} helper: expected bounded invalid UTF-8 failure; " \
                  "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
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
  },
  {
    name: "combined resources require knowledge-augmented",
    fixture: "combined-resources",
    mutate: lambda do |directory|
      replace_selected_profiles.call(directory, "asset-driven, script-assisted")
    end
  },
  {
    name: "combined resources require asset-driven",
    fixture: "combined-resources",
    mutate: lambda do |directory|
      replace_selected_profiles.call(directory, "knowledge-augmented, script-assisted")
    end
  },
  {
    name: "combined resources require script-assisted",
    fixture: "combined-resources",
    mutate: lambda do |directory|
      replace_selected_profiles.call(directory, "knowledge-augmented, asset-driven")
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
