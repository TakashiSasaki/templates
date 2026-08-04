#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "find"
require "open3"
require "pathname"
require "rbconfig"
require "tmpdir"

SOURCE_ROOT = File.expand_path("../..", __dir__)
SMOKES = {
  ".github/scripts/test-minimal-profile-layouts.rb" => "Minimal profile repository layout tests passed.",
  ".github/scripts/test-template-adoption.rb" => "Template adoption smoke tests passed.",
  ".github/scripts/test-concrete-skill-completion.rb" => "Concrete skill completion hygiene tests passed.",
  ".github/scripts/test-installation-modes.rb" => "Installation mode smoke tests passed.",
  ".github/scripts/test-parent-owned-vendoring.rb" => "Parent-owned vendoring smoke tests passed.",
  ".github/scripts/test-non-mutating-consumption.rb" => "Non-mutating skill consumption smoke tests passed."
}.freeze

failures = []

def tree_snapshot(root)
  root_path = Pathname.new(root)
  Find.find(root).sort.each_with_object({}) do |path, snapshot|
    relative = path == root ? "." : Pathname.new(path).relative_path_from(root_path).to_s
    stat = File.lstat(path)
    type = if stat.directory?
             "directory"
           elsif stat.file?
             "file"
           elsif stat.symlink?
             "symlink"
           else
             "other"
           end
    record = [type, stat.mode & 0o7777, stat.mtime.to_r]
    record << File.binread(path) if stat.file?
    record << File.readlink(path) if stat.symlink?
    snapshot[relative] = record
  end
end

Dir.mktmpdir("path-safe-consumption-host") do |host_root|
  path_safe_root = File.join(host_root, "workspace with spaces", "日本語")
  FileUtils.mkdir_p(path_safe_root)
  expected_root = File.realpath(path_safe_root)
  poisoned_git_root = File.join(host_root, "caller-owned git context")
  poisoned_git_dir = File.join(poisoned_git_root, "git dir")
  poisoned_git_worktree = File.join(poisoned_git_root, "work tree")
  poisoned_git_index = File.join(poisoned_git_root, "caller.index")
  FileUtils.mkdir_p([poisoned_git_dir, poisoned_git_worktree])
  File.binwrite(poisoned_git_index, "caller-owned index\n")
  poisoned_before = tree_snapshot(poisoned_git_root)
  environment = {
    "TMPDIR" => path_safe_root,
    "TMP" => path_safe_root,
    "TEMP" => path_safe_root,
    "RUBYOPT" => nil,
    "GIT_DIR" => poisoned_git_dir,
    "GIT_INDEX_FILE" => poisoned_git_index,
    "GIT_WORK_TREE" => poisoned_git_worktree
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
    unless status.success? && stderr.empty? && stdout.lines.last&.strip == success_line
      failures << "#{relative_script} failed under path-safe temporary root: " \
                  "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
    end

    poisoned_after = tree_snapshot(poisoned_git_root)
    unless poisoned_after == poisoned_before
      failures << "#{relative_script} changed caller-owned inherited Git context"
    end
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Path-safe core consumption smoke tests passed."
