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
json_contract_matches = lambda do |parsed, expected_result|
  parsed.is_a?(Hash) &&
    parsed["contractVersion"] == "1" &&
    parsed["ok"] == true &&
    parsed["result"].is_a?(Hash) &&
    expected_result.all? { |field, expected| parsed["result"].key?(field) && parsed["result"][field] == expected }
end

actual_files = Find.find(fixture_root).filter_map do |path|
  next if path == fixture_root || File.directory?(path)

  path.delete_prefix("#{fixture_root}/")
end.sort

if actual_files != expected_files
  failures << "packaged-cli: expected reduced layout #{expected_files.inspect}, got #{actual_files.inspect}"
end

runtime_contract = File.read(File.join(fixture_root, "RUNTIME.md"), encoding: "UTF-8")
documented_install_commands = [
  %q{gem install --no-document --install-dir .local/gems --bindir .local/bin ./text-stat-1.0.0.gem},
  %q{GEM_HOME="$PWD/.local/gems" GEM_PATH="$PWD/.local/gems" PATH="$PWD/.local/bin:$PATH" text-stat --help},
  %q{$env:GEM_HOME="$PWD/.local/gems"; $env:GEM_PATH=$env:GEM_HOME; $env:PATH="$PWD/.local/bin;$env:PATH"; text-stat --help}
].freeze

documented_install_commands.each do |command|
  unless runtime_contract.include?(command)
    failures << "packaged-cli runtime: missing documented installation command #{command.inspect}"
  end
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
    install_root = File.join(directory, ".local")
    gem_home = File.join(install_root, "gems")
    bindir = File.join(install_root, "bin")
    FileUtils.mkdir_p(bindir)

    stdout, stderr, status = Open3.capture3(
      "gem",
      "install",
      "--no-document",
      "--install-dir",
      ".local/gems",
      "--bindir",
      ".local/bin",
      "./text-stat-1.0.0.gem",
      chdir: directory
    )
    unless status.success?
      failures << "packaged-cli install: expected documented local gem install success; stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
    end

    input = File.join(directory, "input.txt")
    File.write(input, "one two\n")
    command = "text-stat"
    environment = {
      "GEM_HOME" => gem_home,
      "GEM_PATH" => gem_home,
      "PATH" => [bindir, ENV["PATH"]].compact.reject(&:empty?).join(File::PATH_SEPARATOR)
    }

    stdout, stderr, status = Open3.capture3(
      environment,
      command,
      "--output",
      "json",
      input,
      chdir: directory
    )
    parsed = JSON.parse(stdout) rescue nil
    expected_result = { "bytes" => 8, "lines" => 1, "words" => 2 }
    unless status.success? && stderr.empty? && json_contract_matches.call(parsed, expected_result)
      failures << "packaged-cli installed command: expected compatible deterministic JSON; " \
                  "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
    end

    stdout, stderr, status = Open3.capture3(
      environment,
      command,
      input,
      chdir: directory
    )
    expected_human = "bytes: 8\nlines: 1\nwords: 2\n"
    unless status.success? && stderr.empty? && stdout == expected_human
      failures << "packaged-cli installed command: expected deterministic human output; " \
                  "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
    end

    invalid_input = File.join(directory, "invalid-utf8.txt")
    File.binwrite(invalid_input, [0xFF].pack("C"))
    stdout, stderr, status = Open3.capture3(
      environment,
      command,
      invalid_input,
      chdir: directory
    )
    unless status.exitstatus == 2 && stdout.empty? && stderr == "input is not valid UTF-8\n"
      failures << "packaged-cli installed command: expected invalid UTF-8 rejection; " \
                  "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
    end

    if File.writable?("/dev/full")
      diagnostic = File.join(directory, "output-write-error.txt")
      process = Process.spawn(
        environment,
        command,
        input,
        out: "/dev/full",
        err: diagnostic,
        chdir: directory
      )
      _pid, status = Process.wait2(process)
      stderr = File.read(diagnostic)
      unless status.exitstatus == 5 && stderr.start_with?("unable to write output: ")
        failures << "packaged-cli installed command: expected output write failure; " \
                    "status=#{status.exitstatus.inspect}, stderr=#{stderr.inspect}"
      end
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
