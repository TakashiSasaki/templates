#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "find"
require "open3"
require "pathname"
require "rbconfig"
require "tmpdir"

SOURCE_ROOT = File.expand_path("../..", __dir__)
NON_MUTATING_SMOKE = ".github/scripts/test-non-mutating-consumption.rb"
SMOKES = {
  ".github/scripts/test-minimal-profile-layouts.rb" => "Minimal profile repository layout tests passed.",
  ".github/scripts/test-copyable-template-consumption.rb" => "Copyable template adoption and installation tests passed.",
  ".github/scripts/test-concrete-skill-completion.rb" => "Concrete skill completion hygiene tests passed.",
  ".github/scripts/test-parent-owned-vendoring.rb" => "Parent-owned vendoring smoke tests passed.",
  NON_MUTATING_SMOKE => "Non-mutating skill consumption smoke tests passed."
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
  poison_root = File.join(host_root, "caller-owned-git-context")
  poison_git_dir = File.join(poison_root, "git-dir")
  poison_work_tree = File.join(poison_root, "work-tree")
  poison_index = File.join(poison_root, "index")
  FileUtils.mkdir_p([path_safe_root, poison_git_dir, poison_work_tree])
  File.binwrite(poison_index, "caller-owned index sentinel\n")
  File.binwrite(File.join(poison_git_dir, "sentinel"), "git-dir sentinel\n")
  File.binwrite(File.join(poison_work_tree, "sentinel"), "work-tree sentinel\n")
  poison_before = tree_snapshot(poison_root)

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
    smoke_environment = environment
    if relative_script == NON_MUTATING_SMOKE
      smoke_environment = environment.merge(
        "GIT_DIR" => poison_git_dir,
        "GIT_INDEX_FILE" => poison_index,
        "GIT_WORK_TREE" => poison_work_tree
      )
    end

    stdout, stderr, status = Open3.capture3(
      smoke_environment,
      RbConfig.ruby,
      relative_script,
      chdir: SOURCE_ROOT
    )
    unless status.success? && stderr.empty? && stdout.lines.last&.strip == success_line
      failures << "#{relative_script} failed under path-safe temporary root: " \
                  "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
    end

    if relative_script == NON_MUTATING_SMOKE && tree_snapshot(poison_root) != poison_before
      failures << "#{relative_script} mutated inherited caller-owned Git context"
    end
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Path-safe core consumption smoke tests passed."
