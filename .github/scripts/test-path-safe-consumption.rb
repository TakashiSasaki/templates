#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "rbconfig"
require "tmpdir"

SOURCE_ROOT = File.expand_path("../..", __dir__)
SMOKES = {
  ".github/scripts/test-minimal-profile-layouts.rb" => "Minimal profile repository layout tests passed.",
  ".github/scripts/test-template-adoption.rb" => "Template adoption smoke tests passed.",
  ".github/scripts/test-installation-modes.rb" => "Installation mode smoke tests passed.",
  ".github/scripts/test-parent-owned-vendoring.rb" => "Parent-owned vendoring smoke tests passed."
}.freeze

failures = []

Dir.mktmpdir("path-safe-consumption-host") do |host_root|
  path_safe_root = File.join(host_root, "workspace with spaces", "日本語")
  FileUtils.mkdir_p(path_safe_root)
  expected_root = File.realpath(path_safe_root)
  environment = {
    "TMPDIR" => path_safe_root,
    "TMP" => path_safe_root,
    "TEMP" => path_safe_root,
    "RUBYOPT" => nil
  }

  stdout, stderr, status = Open3.capture3(
    environment,
    RbConfig.ruby,
    "-rtmpdir",
    "-e",
    "print File.realpath(Dir.tmpdir)",
    chdir: SOURCE_ROOT
  )
  unless status.success? && stderr.empty? && stdout == expected_root
    failures << "temporary-root selection failed: status=#{status.exitstatus.inspect}, " \
                "stdout=#{stdout.inspect}, stderr=#{stderr.inspect}, expected=#{expected_root.inspect}"
  end

  SMOKES.each do |relative_script, success_line|
    stdout, stderr, status = Open3.capture3(
      environment,
      RbConfig.ruby,
      relative_script,
      chdir: SOURCE_ROOT
    )
    next if status.success? && stderr.empty? && stdout.lines.last&.strip == success_line

    failures << "#{relative_script} failed under path-safe temporary root: " \
                "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Path-safe core consumption smoke tests passed."
