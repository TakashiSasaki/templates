#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "find"
require "json"
require "open3"
require "tempfile"
require "timeout"
require "tmpdir"

CommandResult = Struct.new(:stdout, :stderr, :status, :timed_out, keyword_init: true)

source_root = File.expand_path("../..", __dir__)
fixture_root = File.join(source_root, ".github/fixtures/profiles/mcp-apps-enabled")
validator = File.join(source_root, "template/.github/scripts/validate_skill_repository.py")
expected_files = %w[
  INTERFACES.md
  MCP_APPS.md
  MCP_INTERFACE.md
  RUNTIME.md
  SKILL.md
  docs/mcp-transports.md
  mcp/apps/host_bridge.mjs
  mcp/apps/result.html
  mcp/server.mjs
  package.json
  src/text_stats.mjs
  tests/test_mcp_apps.mjs
].sort.freeze

run_command = lambda do |*command, chdir:, timeout_seconds:, env: {}|
  stdout_file = Tempfile.new("mcp-apps-fixture-stdout")
  stderr_file = Tempfile.new("mcp-apps-fixture-stderr")
  status = nil
  timed_out = false
  pid = nil

  begin
    pid = Process.spawn(
      env,
      *command,
      chdir: chdir,
      in: File::NULL,
      out: stdout_file.path,
      err: stderr_file.path,
      pgroup: true
    )
    begin
      Timeout.timeout(timeout_seconds) do
        _waited_pid, status = Process.wait2(pid)
      end
    rescue Timeout::Error
      timed_out = true
      begin
        Process.kill("TERM", -pid)
      rescue Errno::ESRCH
        nil
      end
      begin
        Timeout.timeout(2) { _waited_pid, status = Process.wait2(pid) }
      rescue Timeout::Error
        begin
          Process.kill("KILL", -pid)
        rescue Errno::ESRCH
          nil
        end
        _waited_pid, status = Process.wait2(pid)
      rescue Errno::ECHILD
        nil
      end
    end
  rescue Errno::ENOENT => error
    return CommandResult.new(stdout: "", stderr: "#{error.message}\n", status: nil, timed_out: false)
  ensure
    stdout_file.flush
    stderr_file.flush
  end

  CommandResult.new(
    stdout: File.binread(stdout_file.path),
    stderr: File.binread(stderr_file.path),
    status: status,
    timed_out: timed_out
  )
ensure
  stdout_file&.close!
  stderr_file&.close!
end

failures = []
actual_files = Find.find(fixture_root).filter_map do |path|
  next if path == fixture_root || File.directory?(path)

  path.delete_prefix("#{fixture_root}/")
end.sort
failures << "mcp-apps-enabled layout drift: #{actual_files.inspect}" unless actual_files == expected_files

begin
  manifest = JSON.parse(File.read(File.join(fixture_root, "package.json"), encoding: "UTF-8"))
  dependencies = manifest.fetch("dependencies")
  {
    "@modelcontextprotocol/server" => "2.0.0",
    "@modelcontextprotocol/client" => "2.0.0",
    "zod" => "4.1.13"
  }.each do |package, version|
    failures << "mcp-apps-enabled: expected exact #{package}=#{version} pin" unless dependencies[package] == version
  end
rescue JSON::ParserError, KeyError => error
  failures << "mcp-apps-enabled package.json: #{error.message}"
end

runtime = File.read(File.join(fixture_root, "RUNTIME.md"), encoding: "UTF-8")
failures << "mcp-apps-enabled: missing core 2026-07-28 selection" unless runtime.include?("| Supported protocol revisions | `2026-07-28` |")
failures << "mcp-apps-enabled: missing exact Apps extension selection" unless runtime.include?("| Optional MCP extensions | io.modelcontextprotocol/ui |")
apps = File.read(File.join(fixture_root, "MCP_APPS.md"), encoding: "UTF-8")
failures << "mcp-apps-enabled: missing Apps 2026-01-26 revision" unless apps.include?("Extension specification revision: 2026-01-26")
failures << "mcp-apps-enabled: must remain independent of browser-interface" if File.exist?(File.join(fixture_root, "WEB_INTERFACE.md"))

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

Dir.mktmpdir("mcp-apps-profile") do |directory|
  FileUtils.cp_r("#{fixture_root}/.", directory)
  run_command.call("git", "init", "--quiet", chdir: directory, timeout_seconds: 10)
  run_command.call("git", "add", ".", chdir: directory, timeout_seconds: 10)

  validation = run_command.call(
    "python3", validator, directory,
    chdir: source_root,
    timeout_seconds: 60,
    env: { "RUBYOPT" => nil }
  )
  unless validation.status&.success? && !validation.timed_out
    failures << "mcp-apps-enabled contract validation failed: stdout=#{validation.stdout.inspect}, stderr=#{validation.stderr.inspect}, timed_out=#{validation.timed_out}"
  end

  install = run_command.call(
    "npm", "install", "--ignore-scripts", "--no-audit", "--no-fund",
    chdir: directory,
    timeout_seconds: 180
  )
  unless install.status&.success? && !install.timed_out
    failures << "mcp-apps-enabled npm install failed: stdout=#{install.stdout.inspect}, stderr=#{install.stderr.inspect}, timed_out=#{install.timed_out}"
  end

  if install.status&.success?
    %w[check test].each do |script|
      result = run_command.call("npm", "run", script, chdir: directory, timeout_seconds: 120)
      unless result.status&.success? && !result.timed_out
        failures << "mcp-apps-enabled npm run #{script} failed: stdout=#{result.stdout.inspect}, stderr=#{result.stderr.inspect}, timed_out=#{result.timed_out}"
      end
    end
  end
end

Dir.mktmpdir("invalid-mcp-apps-profile") do |directory|
  FileUtils.cp_r("#{fixture_root}/.", directory)
  File.delete(File.join(directory, "MCP_APPS.md"))
  run_command.call("git", "init", "--quiet", chdir: directory, timeout_seconds: 10)
  run_command.call("git", "add", ".", chdir: directory, timeout_seconds: 10)

  validation = run_command.call(
    "python3", validator, directory,
    chdir: source_root,
    timeout_seconds: 60,
    env: { "RUBYOPT" => nil }
  )
  if validation.timed_out || validation.status&.success?
    failures << "mcp-apps-enabled negative contract: selected Apps without MCP_APPS.md must fail"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "MCP Apps executable fixture tests passed."
