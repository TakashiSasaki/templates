#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "find"
require "open3"
require "rbconfig"
require "tempfile"
require "timeout"
require "tmpdir"

CommandResult = Struct.new(:stdout, :stderr, :status, :timed_out, keyword_init: true)

fixture_root = File.expand_path("../fixtures/profiles/mcp-enabled", __dir__)
validator = File.expand_path("validate-skill-repository.rb", __dir__)
expected_files = %w[
  Gemfile
  INTERFACES.md
  MCP_INTERFACE.md
  RUNTIME.md
  SKILL.md
  docs/mcp-transports.md
  mcp/README.md
  mcp/http_server.rb
  mcp/server.rb
  mcp/server_factory.rb
  src/text_stats.rb
  tests/test_http_boundaries.rb
  tests/test_http_lifecycle.rb
  tests/test_http_server.rb
  tests/test_mcp_server.rb
].sort.freeze

terminate_and_wait = lambda do |pid|
  process_group = -pid
  begin
    Process.kill("TERM", process_group)
  rescue Errno::ESRCH
    nil
  end

  status = begin
    Timeout.timeout(1) do
      _waited_pid, waited_status = Process.wait2(pid)
      waited_status
    end
  rescue Timeout::Error
    begin
      Process.kill("KILL", process_group)
    rescue Errno::ESRCH
      nil
    end
    _waited_pid, waited_status = Process.wait2(pid)
    waited_status
  rescue Errno::ECHILD
    nil
  end

  begin
    Process.kill("KILL", process_group)
  rescue Errno::ESRCH
    nil
  end

  status
end

run_command = lambda do |*command, chdir:, timeout_seconds:, env: {}|
  stdout_file = Tempfile.new("mcp-fixture-stdout")
  stderr_file = Tempfile.new("mcp-fixture-stderr")
  status = nil
  timed_out = false
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
  rescue Errno::ENOENT => error
    return CommandResult.new(
      stdout: "",
      stderr: "#{error.message}\n",
      status: nil,
      timed_out: false
    )
  end

  begin
    Timeout.timeout(timeout_seconds) do
      _waited_pid, status = Process.wait2(pid)
    end
  rescue Timeout::Error
    timed_out = true
    status = terminate_and_wait.call(pid)
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

if actual_files != expected_files
  failures << "mcp-enabled: expected reduced layout #{expected_files.inspect}, got #{actual_files.inspect}"
end

runtime_contract = File.read(File.join(fixture_root, "RUNTIME.md"), encoding: "UTF-8")
documented_commands = [
  "bundle install",
  "bundle exec ruby mcp/server.rb",
  "bundle exec ruby mcp/http_server.rb",
  "bundle exec ruby tests/test_mcp_server.rb",
  "bundle exec ruby tests/test_http_server.rb",
  "bundle exec ruby tests/test_http_boundaries.rb",
  "bundle exec ruby tests/test_http_lifecycle.rb",
  "bundle exec ruby tests/test_mcp_server.rb --name test_initialization_and_tool_inventory",
  "bundle exec ruby tests/test_mcp_server.rb --name test_successful_tool_call",
  "bundle exec ruby tests/test_mcp_server.rb --name test_sequential_tool_calls",
  "bundle exec ruby tests/test_http_server.rb --name test_http_inventory_calls_and_stdio_equivalence",
  "bundle exec ruby tests/test_http_server.rb --name test_request_scoped_host_origin_and_authentication_on_reused_connection",
  "curl --fail --silent --show-error http://127.0.0.1:4570/readyz"
].freeze

documented_commands.each do |command|
  unless runtime_contract.include?(command)
    failures << "mcp-enabled runtime: missing documented command #{command.inspect}"
  end
end

manifest = File.read(File.join(fixture_root, "Gemfile"), encoding: "UTF-8")
{
  'gem "mcp", "1.0.0"' => "official MCP SDK",
  'gem "rack", "3.2.1"' => "Rack interface",
  'gem "rackup", "2.2.1"' => "Rack server handler",
  'gem "webrick", "1.9.1"' => "loopback HTTP server"
}.each do |declaration, purpose|
  failures << "mcp-enabled dependencies: missing exact #{purpose} declaration #{declaration.inspect}" unless manifest.include?(declaration)
end

bundle_check = run_command.call("bundle", "--version", chdir: fixture_root, timeout_seconds: 10)
if bundle_check.timed_out || !bundle_check.status&.success?
  failures << "mcp-enabled dependencies: Bundler is required by the fixture workflow; stderr=#{bundle_check.stderr.inspect}"
end

if failures.empty?
  Dir.mktmpdir("mcp-enabled-profile") do |directory|
    FileUtils.cp_r("#{fixture_root}/.", directory)
    run_command.call("git", "init", "--quiet", chdir: directory, timeout_seconds: 10)
    run_command.call("git", "add", ".", chdir: directory, timeout_seconds: 10)

    validation = run_command.call(
      RbConfig.ruby,
      validator,
      chdir: directory,
      timeout_seconds: 30,
      env: { "RUBYOPT" => nil }
    )
    unless validation.status&.success? && !validation.timed_out
      failures << "mcp-enabled: expected complete repository validation to pass; " \
                  "stdout=#{validation.stdout.inspect}, stderr=#{validation.stderr.inspect}, " \
                  "timed_out=#{validation.timed_out}"
    end

    bundle_config = run_command.call(
      "bundle",
      "config",
      "set",
      "--local",
      "path",
      ".bundle",
      chdir: directory,
      timeout_seconds: 30
    )
    unless bundle_config.status&.success? && !bundle_config.timed_out
      failures << "mcp-enabled dependencies: expected local Bundler path configuration to pass; " \
                  "stderr=#{bundle_config.stderr.inspect}"
    end

    bundle_install = run_command.call(
      "bundle",
      "install",
      "--jobs",
      "4",
      "--retry",
      "3",
      chdir: directory,
      timeout_seconds: 180
    )
    unless bundle_install.status&.success? && !bundle_install.timed_out
      failures << "mcp-enabled dependencies: expected bundle install success; " \
                  "stdout=#{bundle_install.stdout.inspect}, stderr=#{bundle_install.stderr.inspect}, " \
                  "timed_out=#{bundle_install.timed_out}"
    end

    if bundle_install.status&.success?
      %w[
        src/text_stats.rb
        mcp/server_factory.rb
        mcp/server.rb
        mcp/http_server.rb
        tests/test_mcp_server.rb
        tests/test_http_server.rb
        tests/test_http_boundaries.rb
        tests/test_http_lifecycle.rb
      ].each do |path|
        syntax = run_command.call(
          RbConfig.ruby,
          "-c",
          path,
          chdir: directory,
          timeout_seconds: 10
        )
        unless syntax.status&.success? && !syntax.timed_out
          failures << "mcp-enabled syntax: expected #{path} to parse; stderr=#{syntax.stderr.inspect}"
        end
      end

      {
        "stdio" => "tests/test_mcp_server.rb",
        "Streamable HTTP" => "tests/test_http_server.rb",
        "Streamable HTTP boundaries" => "tests/test_http_boundaries.rb",
        "Streamable HTTP lifecycle" => "tests/test_http_lifecycle.rb"
      }.each do |name, test_path|
        tests = run_command.call(
          "bundle",
          "exec",
          RbConfig.ruby,
          test_path,
          chdir: directory,
          timeout_seconds: 120
        )
        unless tests.status&.success? && !tests.timed_out
          failures << "mcp-enabled #{name} tests: expected success; stdout=#{tests.stdout.inspect}, " \
                      "stderr=#{tests.stderr.inspect}, timed_out=#{tests.timed_out}"
        end
      end

      factory_path = File.join(directory, "mcp/server_factory.rb")
      missing_factory_path = "#{factory_path}.missing"
      File.rename(factory_path, missing_factory_path)
      %w[mcp/server.rb mcp/http_server.rb].each do |entry_point|
        missing_factory = run_command.call(
          "bundle",
          "exec",
          RbConfig.ruby,
          entry_point,
          chdir: directory,
          timeout_seconds: 10,
          env: {
            "TEXT_STATS_MCP_HTTP_TOKEN" => "fixture-http-token-0123456789abcdef"
          }
        )
        if missing_factory.timed_out || missing_factory.status&.success? || missing_factory.stderr.strip.empty?
          failures << "mcp-enabled shared implementation: expected #{entry_point} to fail promptly when server_factory.rb is missing; " \
                      "status=#{missing_factory.status&.exitstatus.inspect}, stderr=#{missing_factory.stderr.inspect}, " \
                      "timed_out=#{missing_factory.timed_out}"
        end
      end
      File.rename(missing_factory_path, factory_path)

      %w[mcp/server.rb mcp/http_server.rb].each do |entry_point|
        implementation_path = File.join(directory, entry_point)
        missing_path = "#{implementation_path}.missing"
        File.rename(implementation_path, missing_path)
        missing_implementation = run_command.call(
          "bundle",
          "exec",
          RbConfig.ruby,
          entry_point,
          chdir: directory,
          timeout_seconds: 10,
          env: {
            "TEXT_STATS_MCP_HTTP_TOKEN" => "fixture-http-token-0123456789abcdef"
          }
        )
        if missing_implementation.timed_out || missing_implementation.status&.success? ||
           missing_implementation.stderr.strip.empty?
          failures << "mcp-enabled missing implementation: expected #{entry_point} to fail promptly with diagnostics; " \
                      "status=#{missing_implementation.status&.exitstatus.inspect}, " \
                      "stderr=#{missing_implementation.stderr.inspect}, timed_out=#{missing_implementation.timed_out}"
        end
        File.rename(missing_path, implementation_path)
      end
    end
  end
end

Dir.mktmpdir("invalid-mcp-enabled-profile") do |directory|
  FileUtils.cp_r("#{fixture_root}/.", directory)
  File.delete(File.join(directory, "MCP_INTERFACE.md"))
  run_command.call("git", "init", "--quiet", chdir: directory, timeout_seconds: 10)
  run_command.call("git", "add", ".", chdir: directory, timeout_seconds: 10)

  validation = run_command.call(
    RbConfig.ruby,
    validator,
    chdir: directory,
    timeout_seconds: 30,
    env: { "RUBYOPT" => nil }
  )
  if validation.timed_out || validation.status&.success?
    failures << "mcp-enabled invalid contract: expected missing MCP_INTERFACE.md to fail repository validation"
  elsif validation.stderr.strip.empty?
    failures << "mcp-enabled invalid contract: expected an actionable diagnostic for the missing required contract"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "MCP-enabled stdio and Streamable HTTP profile fixture tests passed."
