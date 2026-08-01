#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "find"
require "json"
require "open3"
require "rbconfig"
require "tmpdir"

fixture_root = File.expand_path("../fixtures/profiles/packaged-cli", __dir__)
validator = File.expand_path("validate-skill-repository.rb", __dir__)
expected_files = %w[
  CLI_INTERFACE.md
  Gemfile
  Gemfile.lock
  INTERFACES.md
  RUNTIME.md
  SKILL.md
  bin/text-stat
  src/text_stat.rb
  tests/test_text_stat.rb
  text-stat.gemspec
].sort.freeze

failures = []

actual_files = Find.find(fixture_root).filter_map do |path|
  next if path == fixture_root || File.directory?(path)

  path.delete_prefix("#{fixture_root}/")
end.sort

if actual_files != expected_files
  failures << "packaged-cli: expected reduced layout #{expected_files.inspect}, got #{actual_files.inspect}"
end

Dir.mktmpdir("packaged-cli-profile") do |directory|
  FileUtils.cp_r("#{fixture_root}/.", directory)
  Open3.capture3("git", "init", "--quiet", chdir: directory)
  Open3.capture3("git", "add", ".", chdir: directory)

  _stdout, stderr, status = Open3.capture3(
    { "RUBYOPT" => nil },
    RbConfig.ruby,
    validator,
    chdir: directory
  )
  unless status.success?
    failures << "packaged-cli: expected complete repository validation to pass; diagnostics=#{stderr.strip.inspect}"
  end

  stdout, stderr, status = Open3.capture3(
    RbConfig.ruby,
    "tests/test_text_stat.rb",
    chdir: directory
  )
  unless status.success?
    failures << "packaged-cli tests: expected success; stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
  end

  package = File.join(directory, "text-stat-1.0.0.gem")
  stdout, stderr, status = Open3.capture3(
    "gem",
    "build",
    "text-stat.gemspec",
    "--output",
    package,
    chdir: directory
  )
  unless status.success? && File.file?(package)
    failures << "packaged-cli package: expected gem build success; stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
  end

  if File.file?(package)
    install_root = File.join(directory, "installed")
    gem_home = File.join(install_root, "gems")
    bindir = File.join(install_root, "bin")
    FileUtils.mkdir_p(bindir)

    stdout, stderr, status = Open3.capture3(
      "gem",
      "install",
      "--no-document",
      "--install-dir",
      gem_home,
      "--bindir",
      bindir,
      package,
      chdir: directory
    )
    unless status.success?
      failures << "packaged-cli install: expected isolated gem install success; stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
    end

    input = File.join(directory, "input.txt")
    File.write(input, "one two\n")
    command = File.join(bindir, "text-stat")
    stdout, stderr, status = Open3.capture3(
      { "GEM_HOME" => gem_home, "GEM_PATH" => gem_home },
      command,
      "--output",
      "json",
      input,
      chdir: directory
    )
    expected = {
      "contractVersion" => "1",
      "ok" => true,
      "result" => { "bytes" => 8, "lines" => 1, "words" => 2 }
    }
    parsed = JSON.parse(stdout) rescue nil
    unless status.success? && stderr.empty? && parsed == expected
      failures << "packaged-cli installed command: expected deterministic JSON; " \
                  "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
    end
  end
end

Dir.mktmpdir("invalid-packaged-cli-profile") do |directory|
  FileUtils.cp_r("#{fixture_root}/.", directory)
  File.delete(File.join(directory, "src/text_stat.rb"))
  Open3.capture3("git", "init", "--quiet", chdir: directory)
  Open3.capture3("git", "add", ".", chdir: directory)
  _stdout, stderr, status = Open3.capture3(
    { "RUBYOPT" => nil },
    RbConfig.ruby,
    validator,
    chdir: directory
  )
  if status.success?
    failures << "packaged-cli invalid fixture: expected missing source implementation to fail"
  elsif stderr.strip.empty?
    failures << "packaged-cli invalid fixture: expected an actionable missing-source diagnostic"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Packaged CLI profile fixture tests passed."
