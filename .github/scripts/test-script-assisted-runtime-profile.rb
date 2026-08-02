#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "find"
require "open3"
require "rbconfig"
require "tmpdir"

fixture_root = File.expand_path("../fixtures/profiles/script-assisted-runtime", __dir__)
validator = File.expand_path("validate-skill-repository.rb", __dir__)
expected_files = %w[
  RUNTIME.md
  SKILL.md
  scripts/normalize.rb
].sort.freeze
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

copy_fixture = lambda do |directory|
  FileUtils.cp_r("#{fixture_root}/.", directory)
end

actual_files = Find.find(fixture_root).filter_map do |path|
  next if path == fixture_root || File.directory?(path)

  path.delete_prefix("#{fixture_root}/")
end.sort

if actual_files != expected_files
  failures << "script-assisted-runtime: expected reduced layout #{expected_files.inspect}, got #{actual_files.inspect}"
end

runtime = File.read(File.join(fixture_root, "RUNTIME.md"), encoding: "UTF-8")
[
  "Selection status: SELECTED",
  "| Runtime | CRuby |",
  "| Minimum runtime version | 3.1 |",
  "| Project manifest | NONE |",
  "| Lockfile policy | NONE |",
  "| Run in place | `ruby scripts/normalize.rb INPUT OUTPUT` |",
  "| Build/package | NOT APPLICABLE |"
].each do |required_text|
  unless runtime.include?(required_text)
    failures << "script-assisted-runtime: missing runtime authority #{required_text.inspect}"
  end
end

helper_source = File.read(
  File.join(fixture_root, "scripts/normalize.rb"),
  encoding: "UTF-8"
)
unless helper_source.include?("File.binwrite(output_path, normalized)")
  failures << "script-assisted-runtime: helper output must use File.binwrite to preserve LF bytes on Windows"
end

Dir.mktmpdir("script-assisted-runtime-profile") do |directory|
  copy_fixture.call(directory)
  _stdout, stderr, status = run_validator.call(directory)
  unless status.success?
    failures << "script-assisted-runtime: expected complete repository validation to pass; diagnostics=#{stderr.strip.inspect}"
  end

  syntax_stdout, syntax_stderr, syntax_status = Open3.capture3(
    RbConfig.ruby,
    "-c",
    "scripts/normalize.rb",
    chdir: directory
  )
  unless syntax_status.success? && syntax_stdout == "Syntax OK\n" && syntax_stderr.empty?
    failures << "script-assisted-runtime syntax: expected success; stdout=#{syntax_stdout.inspect}, stderr=#{syntax_stderr.inspect}"
  end

  input_path = File.join(directory, "input.txt")
  File.binwrite(input_path, "alpha  \r\nbeta\t\r\n")
  input_before = File.binread(input_path)
  stdout, helper_stderr, helper_status = Open3.capture3(
    RbConfig.ruby,
    "scripts/normalize.rb",
    "input.txt",
    "output.txt",
    chdir: directory
  )
  output_path = File.join(directory, "output.txt")
  output = File.binread(output_path) if File.file?(output_path)
  unless helper_status.success? && stdout == "output.txt\n" && helper_stderr.empty? &&
         output == "alpha\nbeta\n" && File.binread(input_path) == input_before
    failures << "script-assisted-runtime helper: expected deterministic output without input mutation; " \
                "status=#{helper_status.exitstatus.inspect}, stdout=#{stdout.inspect}, " \
                "stderr=#{helper_stderr.inspect}, output=#{output.inspect}"
  end

  File.binwrite(File.join(directory, "invalid.txt"), [0xFF].pack("C"))
  stdout, helper_stderr, helper_status = Open3.capture3(
    RbConfig.ruby,
    "scripts/normalize.rb",
    "invalid.txt",
    "invalid-output.txt",
    chdir: directory
  )
  unless helper_status.exitstatus == 3 && stdout.empty? && helper_stderr == "invalid UTF-8 input\n" &&
         !File.exist?(File.join(directory, "invalid-output.txt"))
    failures << "script-assisted-runtime helper: expected bounded invalid UTF-8 failure; " \
                "status=#{helper_status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{helper_stderr.inspect}"
  end
end

[
  {
    name: "rejects an unselected retained runtime",
    mutate: lambda do |directory|
      path = File.join(directory, "RUNTIME.md")
      File.write(path, File.read(path).sub("Selection status: SELECTED", "Selection status: UNSELECTED"))
    end,
    diagnostic: "Selection status: SELECTED"
  },
  {
    name: "rejects a runtime placeholder",
    mutate: lambda do |directory|
      path = File.join(directory, "RUNTIME.md")
      File.write(path, File.read(path).sub("| Runtime | CRuby |", "| Runtime | TBD |"))
    end,
    diagnostic: "unresolved scalar placeholder \"TBD\""
  }
].each do |test_case|
  Dir.mktmpdir("invalid-script-assisted-runtime-profile") do |directory|
    copy_fixture.call(directory)
    test_case.fetch(:mutate).call(directory)
    _stdout, stderr, status = run_validator.call(directory)
    if status.success?
      failures << "script-assisted-runtime #{test_case.fetch(:name)}: expected repository validation failure"
    elsif !stderr.include?(test_case.fetch(:diagnostic))
      failures << "script-assisted-runtime #{test_case.fetch(:name)}: expected actionable diagnostic containing " \
                  "#{test_case.fetch(:diagnostic).inspect}; diagnostics=#{stderr.inspect}"
    end
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Script-assisted optional-runtime profile fixture tests passed."
