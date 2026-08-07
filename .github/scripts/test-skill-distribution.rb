#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "json"
require "open3"
require "rbconfig"
require "tmpdir"

SOURCE_ROOT = File.expand_path("../..", __dir__)
VALIDATOR = File.join(SOURCE_ROOT, ".github/scripts/validate-skill-distribution.rb")

failures = []

run_validator = lambda do |root|
  Open3.capture3({ "RUBYOPT" => nil }, RbConfig.ruby, VALIDATOR, root, chdir: root)
end

stdout, stderr, status = run_validator.call(SOURCE_ROOT)
unless status.success? && stderr.empty? && stdout.include?("Skill template distribution is valid.")
  failures << "canonical distribution: status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
end

copy_source = lambda do |target|
  FileUtils.mkdir_p(target)
  Dir.children(SOURCE_ROOT).sort.each do |entry|
    next if entry == ".git"

    FileUtils.cp_r(File.join(SOURCE_ROOT, entry), File.join(target, entry), preserve: true)
  end
  [["git", "init", "--quiet"], ["git", "add", "."]].each do |command|
    _stdout, command_stderr, command_status = Open3.capture3(*command, chdir: target)
    raise "#{command.join(' ')} failed: #{command_stderr}" unless command_status.success?
  end
end

expect_failure = lambda do |label, expected, &mutation|
  raise ArgumentError, "negative test mutation is required" unless mutation

  Dir.mktmpdir("skill-distribution-negative") do |temporary|
    copy_source.call(temporary)
    mutation.call(temporary)
    Open3.capture3("git", "add", "-A", chdir: temporary)
    stdout, stderr, status = run_validator.call(temporary)
    failures << "#{label}: validation unexpectedly succeeded: #{stdout.inspect}" if status.success?
    failures << "#{label}: missing diagnostic #{expected.inspect}: #{stderr.inspect}" unless stderr.include?(expected)
  end
end

expect_failure.call("missing declared file", "declared files are missing") do |root|
  File.delete(File.join(root, "template", "SKILL.md"))
end

expect_failure.call("mirrored validator drift", "mirrored bytes differ") do |root|
  path = File.join(root, "template", ".github", "scripts", "validate_skill_repository.py")
  File.open(path, "a", encoding: "UTF-8") { |file| file << "\n# DRIFT\n" }
end

expect_failure.call("owned inventory omission", "undeclared files are present") do |root|
  path = File.join(root, "distribution-manifest.json")
  manifest = JSON.parse(File.read(path, encoding: "UTF-8"))
  manifest.fetch("distribution_owned_files").delete("RUNTIME.md")
  File.write(path, JSON.pretty_generate(manifest) + "\n", encoding: "UTF-8")
end

expect_failure.call("undeclared distribution file", "undeclared files are present") do |root|
  File.write(File.join(root, "template", "UNDECLARED.txt"), "unexpected\n", encoding: "UTF-8")
end

expect_failure.call("symbolic link", "symbolic links are prohibited") do |root|
  File.symlink("SKILL.md", File.join(root, "template", "LINK.md"))
end

expect_failure.call("transformation enabled", "content transformation must remain disabled") do |root|
  path = File.join(root, "distribution-manifest.json")
  manifest = JSON.parse(File.read(path, encoding: "UTF-8"))
  manifest["content_transformation_allowed"] = true
  File.write(path, JSON.pretty_generate(manifest) + "\n", encoding: "UTF-8")
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Skill template distribution tests passed."
