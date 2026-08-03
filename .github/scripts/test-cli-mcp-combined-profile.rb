#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "find"
require "json"
require "open3"
require "rbconfig"
require "tmpdir"

fixture = File.expand_path("../fixtures/profiles/cli-mcp-combined", __dir__)
validator = File.expand_path("validate-skill-repository.rb", __dir__)
interface_runtime_validator = File.expand_path("validate-interface-runtime-consistency.rb", __dir__)
expected_files = %w[
  CLI_INTERFACE.md Gemfile Gemfile.lock INTERFACES.md MCP_INTERFACE.md RUNTIME.md SKILL.md
  bin/text-stat docs/mcp-transports.md mcp/README.md mcp/server.rb src/text_stat.rb src/text_stats.rb
  tests/test_interface_equivalence.rb tests/test_mcp_server.rb tests/test_text_stat.rb text-stat.gemspec
].sort.freeze

failures = []
run = lambda do |*command, chdir:, env: {}|
  stdout, stderr, status = Open3.capture3(env, *command, chdir: chdir)
  [stdout, stderr, status]
rescue Errno::ENOENT => error
  ["", "#{error.message}\n", nil]
end

actual_files = Find.find(fixture).filter_map do |path|
  next if path == fixture || File.directory?(path)

  path.delete_prefix("#{fixture}/")
end.sort
failures << "cli-mcp-combined: expected #{expected_files.inspect}, got #{actual_files.inspect}" unless actual_files == expected_files

contract_expectations = {
  "SKILL.md" => [
    "Selected profiles: packaged-cli, mcp-enabled",
    "Detailed interface contract: CLI_INTERFACE.md and MCP_INTERFACE.md",
    "Preferred agent route: see INTERFACES.md"
  ],
  "RUNTIME.md" => [
    "`src/text_stat.rb` contains shared domain and CLI logic",
    "| Human CLI | `text-stat` |",
    "| Start stdio MCP server | `bundle exec ruby mcp/server.rb` |",
    "| CLI distribution | Ruby gem `text-stat` with the `text-stat` executable |",
    "| MCP distribution | Bundled with the skill source"
  ],
  "INTERFACES.md" => [
    "Preferred agent interface: native MCP tool already registered in the host",
    "Fallback 1: installed human CLI command",
    "Fallback 2: stable in-place CLI launcher",
    "same `TextStat.analyze` implementation"
  ],
  "src/text_stats.rb" => ["TextStat.analyze(text)"]
}.freeze
contract_expectations.each do |path, required_texts|
  content = File.read(File.join(fixture, path), encoding: "UTF-8")
  required_texts.each do |required_text|
    failures << "#{path}: missing #{required_text.inspect}" unless content.include?(required_text)
  end
end

bundle_stdout, bundle_stderr, bundle_status = run.call("bundle", "--version", chdir: fixture)
unless bundle_status&.success?
  failures << "cli-mcp-combined dependencies: Bundler is required; stdout=#{bundle_stdout.inspect}, stderr=#{bundle_stderr.inspect}"
end

if failures.empty?
  Dir.mktmpdir("cli-mcp-combined-profile") do |directory|
    FileUtils.cp_r("#{fixture}/.", directory)
    run.call("git", "init", "--quiet", chdir: directory)
    run.call("git", "add", ".", chdir: directory)

    stdout, stderr, status = run.call(
      RbConfig.ruby,
      validator,
      chdir: directory,
      env: { "RUBYOPT" => nil }
    )
    failures << "complete repository validation failed: stdout=#{stdout.inspect}, stderr=#{stderr.inspect}" unless status&.success?

    _stdout, stderr, status = run.call("bundle", "config", "set", "--local", "path", ".bundle", chdir: directory)
    failures << "bundle path configuration failed: #{stderr.inspect}" unless status&.success?

    stdout, stderr, status = run.call("bundle", "install", "--jobs", "4", "--retry", "3", chdir: directory)
    unless status&.success?
      failures << "bundle install failed: stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
      next
    end

    %w[
      src/text_stat.rb src/text_stats.rb bin/text-stat mcp/server.rb
      tests/test_text_stat.rb tests/test_mcp_server.rb tests/test_interface_equivalence.rb
    ].each do |path|
      _stdout, stderr, status = run.call(RbConfig.ruby, "-c", path, chdir: directory)
      failures << "syntax failed for #{path}: #{stderr.inspect}" unless status&.success?
    end

    %w[tests/test_text_stat.rb tests/test_mcp_server.rb tests/test_interface_equivalence.rb].each do |path|
      stdout, stderr, status = run.call("bundle", "exec", RbConfig.ruby, path, chdir: directory)
      failures << "tests failed for #{path}: stdout=#{stdout.inspect}, stderr=#{stderr.inspect}" unless status&.success?
    end

    stdout, stderr, status = run.call("gem", "build", "text-stat.gemspec", "--output", "text-stat-1.0.0.gem", chdir: directory)
    failures << "gem build failed: stdout=#{stdout.inspect}, stderr=#{stderr.inspect}" unless status&.success?

    if status&.success?
      stdout, stderr, install_status = run.call(
        "gem", "install", "--no-document", "--install-dir", ".local/gems", "--bindir", ".local/bin",
        "./text-stat-1.0.0.gem", chdir: directory
      )
      failures << "isolated gem install failed: stdout=#{stdout.inspect}, stderr=#{stderr.inspect}" unless install_status&.success?

      if install_status&.success?
        input = File.join(directory, "input.txt")
        File.write(input, "one two\n")
        gem_home = File.join(directory, ".local/gems")
        environment = {
          "GEM_HOME" => gem_home,
          "GEM_PATH" => gem_home,
          "PATH" => [File.join(directory, ".local/bin"), ENV["PATH"]].compact.join(File::PATH_SEPARATOR)
        }
        stdout, stderr, installed_status = run.call(
          "text-stat",
          "--output",
          "json",
          input,
          chdir: directory,
          env: environment
        )
        parsed = JSON.parse(stdout) rescue nil
        expected = { "bytes" => 8, "lines" => 1, "words" => 2 }
        valid = parsed.is_a?(Hash) && parsed["contractVersion"] == "1" &&
                parsed["ok"] == true && parsed["result"] == expected
        unless installed_status&.success? && stderr.empty? && valid
          failures << "installed CLI validation failed: stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
        end
      end
    end
  end
end

%w[CLI_INTERFACE.md MCP_INTERFACE.md].each do |missing_path|
  Dir.mktmpdir("invalid-cli-mcp-combined-profile") do |directory|
    FileUtils.cp_r("#{fixture}/.", directory)
    File.delete(File.join(directory, missing_path))
    run.call("git", "init", "--quiet", chdir: directory)
    run.call("git", "add", ".", chdir: directory)
    _stdout, stderr, status = run.call(
      RbConfig.ruby,
      validator,
      chdir: directory,
      env: { "RUBYOPT" => nil }
    )
    if status&.success? || stderr.strip.empty?
      failures << "missing #{missing_path} did not produce an actionable repository-validation failure"
    end
  end
end

Dir.mktmpdir("invalid-disabled-bundled-client-command") do |directory|
  FileUtils.cp_r("#{fixture}/.", directory)
  runtime_path = File.join(directory, "RUNTIME.md")
  runtime = File.read(runtime_path, encoding: "UTF-8")
  mutated_runtime = runtime.sub(
    "| Stable public command | NOT SUPPORTED |",
    "| Stable public command | ghost-mcp-client |"
  )
  failures << "combined fixture regression setup did not mutate Stable public command" if mutated_runtime == runtime
  File.write(runtime_path, mutated_runtime)

  _stdout, stderr, status = run.call(
    RbConfig.ruby,
    interface_runtime_validator,
    chdir: directory,
    env: { "RUBYOPT" => nil }
  )
  unless !status&.success? && stderr.include?("Stable public command must be 'NOT SUPPORTED'")
    failures << "disabled bundled client with a concrete stable command was not rejected: stderr=#{stderr.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Combined packaged CLI and MCP profile fixture tests passed."
