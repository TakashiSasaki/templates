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

fixture_root = File.expand_path("../fixtures/profiles/mcp-systemd-service", __dir__)
validator = File.expand_path("validate-skill-repository.rb", __dir__)
expected_files = %w[
  Gemfile
  INTERFACES.md
  MCP_INTERFACE.md
  RUNTIME.md
  SKILL.md
  deployment/systemd/render_unit.rb
  deployment/systemd/text-stats-mcp.service.in
  docs/mcp-transports.md
  mcp/http_server.rb
  mcp/server_factory.rb
  src/text_stats.rb
  tests/systemd_smoke.sh
  tests/systemd_smoke_client.rb
  tests/test_http_server.rb
  tests/test_unit_renderer.rb
].sort.freeze

run_command = lambda do |*command, chdir:, timeout_seconds:, env: {}|
  stdout_file = Tempfile.new("mcp-systemd-stdout")
  stderr_file = Tempfile.new("mcp-systemd-stderr")
  status = nil
  timed_out = false
  pid = Process.spawn(env, *command, chdir: chdir, in: File::NULL,
                      out: stdout_file.path, err: stderr_file.path, pgroup: true)
  begin
    Timeout.timeout(timeout_seconds) { _pid, status = Process.wait2(pid) }
  rescue Timeout::Error
    timed_out = true
    begin
      Process.kill("TERM", -pid)
    rescue Errno::ESRCH
      nil
    end
    begin
      Timeout.timeout(1) { _pid, status = Process.wait2(pid) }
    rescue Timeout::Error
      begin
        Process.kill("KILL", -pid)
      rescue Errno::ESRCH
        nil
      end
      _pid, status = Process.wait2(pid)
    end
  ensure
    stdout_file.flush
    stderr_file.flush
  end
  CommandResult.new(stdout: File.binread(stdout_file.path), stderr: File.binread(stderr_file.path),
                    status: status, timed_out: timed_out)
rescue Errno::ENOENT => error
  CommandResult.new(stdout: "", stderr: "#{error.message}\n", status: nil, timed_out: false)
ensure
  stdout_file&.close!
  stderr_file&.close!
end

failures = []
actual_files = Find.find(fixture_root).filter_map do |path|
  next if path == fixture_root || File.directory?(path)

  path.delete_prefix("#{fixture_root}/")
end.sort
failures << "mcp-systemd-service: expected reduced layout #{expected_files.inspect}, got #{actual_files.inspect}" unless actual_files == expected_files

if actual_files == expected_files
  skill = File.read(File.join(fixture_root, "SKILL.md"), encoding: "UTF-8")
  runtime = File.read(File.join(fixture_root, "RUNTIME.md"), encoding: "UTF-8")
  interface = File.read(File.join(fixture_root, "MCP_INTERFACE.md"), encoding: "UTF-8")
  unit = File.read(File.join(fixture_root, "deployment/systemd/text-stats-mcp.service.in"), encoding: "UTF-8")
  manifest = File.read(File.join(fixture_root, "Gemfile"), encoding: "UTF-8")

  failures << "mcp-systemd-service: combined profile selection missing" unless skill.include?("Selected profiles: mcp-enabled, headless-service")
  %w[Type=notify NotifyAccess=main LoadCredential= Restart=on-failure RestartPreventExitStatus=78 KillMode=control-group NoNewPrivileges=yes ProtectSystem=strict].each do |selection|
    failures << "mcp-systemd-service unit: missing #{selection.inspect}" unless unit.include?(selection)
  end
  [
    "bundle install",
    "deployment/systemd/render_unit.rb",
    "systemd-analyze verify",
    "sudo systemctl start text-stats-mcp.service",
    "sudo systemctl stop text-stats-mcp.service",
    "bundle exec bash tests/systemd_smoke.sh"
  ].each do |command|
    failures << "mcp-systemd-service runtime: missing documented command #{command.inspect}" unless runtime.include?(command)
  end
  failures << "mcp-systemd-service interface: expected Streamable HTTP support" unless interface.include?("Supported: YES")
  failures << "mcp-systemd-service interface: expected stdio to remain unsupported" unless interface.include?("## stdio MCP server variant\n\nSupported: NO")
  {
    'gem "mcp", "1.0.0"' => "MCP SDK",
    'gem "rack", "3.2.1"' => "Rack",
    'gem "rackup", "2.2.1"' => "Rackup",
    'gem "webrick", "1.9.1"' => "WEBrick",
    'gem "minitest", "~> 5.20"' => "Minitest"
  }.each do |declaration, purpose|
    failures << "mcp-systemd-service dependencies: missing #{purpose} declaration" unless manifest.include?(declaration)
  end
end

if failures.empty?
  Dir.mktmpdir("mcp-systemd-service-profile") do |directory|
    FileUtils.cp_r("#{fixture_root}/.", directory)
    run_command.call("git", "init", "--quiet", chdir: directory, timeout_seconds: 10)
    run_command.call("git", "add", ".", chdir: directory, timeout_seconds: 10)

    validation = run_command.call(RbConfig.ruby, validator, chdir: directory, timeout_seconds: 30,
                                  env: { "RUBYOPT" => nil })
    unless validation.status&.success? && !validation.timed_out
      failures << "mcp-systemd-service: expected repository validation success; stdout=#{validation.stdout.inspect}, stderr=#{validation.stderr.inspect}, timed_out=#{validation.timed_out}"
    end

    config = run_command.call("bundle", "config", "set", "--local", "path", ".bundle",
                              chdir: directory, timeout_seconds: 30)
    failures << "mcp-systemd-service: bundle path configuration failed: #{config.stderr.inspect}" unless config.status&.success? && !config.timed_out

    install = run_command.call("bundle", "install", "--jobs", "4", "--retry", "3",
                               chdir: directory, timeout_seconds: 180)
    unless install.status&.success? && !install.timed_out
      failures << "mcp-systemd-service: bundle install failed; stdout=#{install.stdout.inspect}, stderr=#{install.stderr.inspect}, timed_out=#{install.timed_out}"
    end

    if install.status&.success?
      %w[
        src/text_stats.rb
        mcp/server_factory.rb
        mcp/http_server.rb
        deployment/systemd/render_unit.rb
        tests/test_unit_renderer.rb
        tests/test_http_server.rb
        tests/systemd_smoke_client.rb
      ].each do |path|
        syntax = run_command.call(RbConfig.ruby, "-c", path, chdir: directory, timeout_seconds: 10)
        failures << "mcp-systemd-service syntax: #{path} failed: #{syntax.stderr.inspect}" unless syntax.status&.success? && !syntax.timed_out
      end
      shell_syntax = run_command.call("bash", "-n", "tests/systemd_smoke.sh", chdir: directory, timeout_seconds: 10)
      failures << "mcp-systemd-service syntax: smoke shell failed: #{shell_syntax.stderr.inspect}" unless shell_syntax.status&.success? && !shell_syntax.timed_out

      {
        "unit renderer" => "tests/test_unit_renderer.rb",
        "HTTP adapter" => "tests/test_http_server.rb"
      }.each do |name, path|
        tests = run_command.call("bundle", "exec", RbConfig.ruby, path, chdir: directory, timeout_seconds: 120)
        unless tests.status&.success? && !tests.timed_out
          failures << "mcp-systemd-service #{name} tests failed; stdout=#{tests.stdout.inspect}, stderr=#{tests.stderr.inspect}, timed_out=#{tests.timed_out}"
        end
      end

      template = File.join(directory, "deployment/systemd/text-stats-mcp.service.in")
      File.rename(template, "#{template}.missing")
      missing = run_command.call("bundle", "exec", RbConfig.ruby, "tests/test_unit_renderer.rb",
                                 chdir: directory, timeout_seconds: 30)
      no_diagnostic = missing.stdout.strip.empty? && missing.stderr.strip.empty?
      if missing.status&.success? || missing.timed_out || no_diagnostic
        failures << "mcp-systemd-service missing deployment artifact: expected prompt tested failure; status=#{missing.status&.exitstatus.inspect}, stdout=#{missing.stdout.inspect}, stderr=#{missing.stderr.inspect}, timed_out=#{missing.timed_out}"
      end
    end
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "MCP systemd service profile fixture tests passed."
