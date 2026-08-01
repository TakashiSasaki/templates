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

fixture_root = File.expand_path("../fixtures/profiles/browser-interface", __dir__)
validator = File.expand_path("validate-skill-repository.rb", __dir__)
expected_files = %w[
  Gemfile
  RUNTIME.md
  SKILL.md
  WEB_INTERFACE.md
  src/text_stats.rb
  tests/test_web_server.rb
  web/server.rb
].sort.freeze

terminate_and_wait = lambda do |pid|
  begin
    Process.kill("TERM", pid)
  rescue Errno::ESRCH
    return nil
  end

  begin
    Timeout.timeout(1) do
      _waited_pid, status = Process.wait2(pid)
      return status
    end
  rescue Timeout::Error
    begin
      Process.kill("KILL", pid)
    rescue Errno::ESRCH
      nil
    end
    _waited_pid, status = Process.wait2(pid)
    status
  rescue Errno::ECHILD
    nil
  end
end

run_command = lambda do |*command, chdir:, timeout_seconds:, env: {}|
  stdout_file = Tempfile.new("browser-fixture-stdout")
  stderr_file = Tempfile.new("browser-fixture-stderr")
  status = nil
  timed_out = false
  begin
    pid = Process.spawn(
      env,
      *command,
      chdir: chdir,
      in: File::NULL,
      out: stdout_file.path,
      err: stderr_file.path
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
  failures << "browser-interface: expected reduced layout #{expected_files.inspect}, got #{actual_files.inspect}"
end

runtime_contract = File.read(File.join(fixture_root, "RUNTIME.md"), encoding: "UTF-8")
documented_commands = [
  "bundle install",
  "TEXT_STATS_WEB_ENABLED=1 bundle exec ruby web/server.rb",
  "bundle exec ruby web/server.rb --stop",
  "bundle exec ruby web/server.rb --health",
  "bundle exec ruby tests/test_web_server.rb"
].freeze

documented_commands.each do |command|
  unless runtime_contract.include?(command)
    failures << "browser-interface runtime: missing documented command #{command.inspect}"
  end
end

bundle_check = run_command.call("bundle", "--version", chdir: fixture_root, timeout_seconds: 10)
if bundle_check.timed_out || !bundle_check.status&.success?
  failures << "browser-interface dependencies: Bundler is required by the fixture workflow; stderr=#{bundle_check.stderr.inspect}"
end

if failures.empty?
  Dir.mktmpdir("browser-interface-profile") do |directory|
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
      failures << "browser-interface: expected complete repository validation to pass; " \
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
      failures << "browser-interface dependencies: expected local Bundler path configuration to pass; " \
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
      failures << "browser-interface dependencies: expected bundle install success; " \
                  "stdout=#{bundle_install.stdout.inspect}, stderr=#{bundle_install.stderr.inspect}, " \
                  "timed_out=#{bundle_install.timed_out}"
    end

    if bundle_install.status&.success?
      %w[src/text_stats.rb web/server.rb tests/test_web_server.rb].each do |path|
        syntax = run_command.call(
          RbConfig.ruby,
          "-c",
          path,
          chdir: directory,
          timeout_seconds: 10
        )
        unless syntax.status&.success? && !syntax.timed_out
          failures << "browser-interface syntax: expected #{path} to parse; stderr=#{syntax.stderr.inspect}"
        end
      end

      tests = run_command.call(
        "bundle",
        "exec",
        RbConfig.ruby,
        "tests/test_web_server.rb",
        chdir: directory,
        timeout_seconds: 90
      )
      unless tests.status&.success? && !tests.timed_out
        failures << "browser-interface tests: expected success; stdout=#{tests.stdout.inspect}, " \
                    "stderr=#{tests.stderr.inspect}, timed_out=#{tests.timed_out}"
      end

      implementation_path = File.join(directory, "src/text_stats.rb")
      missing_path = "#{implementation_path}.missing"
      File.rename(implementation_path, missing_path)
      missing_implementation = run_command.call(
        "bundle",
        "exec",
        RbConfig.ruby,
        "web/server.rb",
        chdir: directory,
        timeout_seconds: 10,
        env: {
          "TEXT_STATS_WEB_ENABLED" => "1",
          "TEXT_STATS_WEB_PORT" => "0",
          "TEXT_STATS_WEB_PID_FILE" => File.join(directory, "missing.pid")
        }
      )
      if missing_implementation.timed_out || missing_implementation.status&.success? ||
         missing_implementation.stderr.strip.empty?
        failures << "browser-interface missing implementation: expected a prompt nonzero failure with diagnostics; " \
                    "status=#{missing_implementation.status&.exitstatus.inspect}, " \
                    "stderr=#{missing_implementation.stderr.inspect}, timed_out=#{missing_implementation.timed_out}"
      end
      File.rename(missing_path, implementation_path)
    end
  end
end

Dir.mktmpdir("invalid-browser-interface-profile") do |directory|
  FileUtils.cp_r("#{fixture_root}/.", directory)
  File.delete(File.join(directory, "WEB_INTERFACE.md"))
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
    failures << "browser-interface invalid contract: expected missing WEB_INTERFACE.md to fail repository validation"
  elsif !validation.stderr.include?("WEB_INTERFACE.md")
    failures << "browser-interface invalid contract: expected an actionable WEB_INTERFACE.md diagnostic; " \
                "stderr=#{validation.stderr.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Browser-interface profile fixture tests passed."
