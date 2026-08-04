#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "find"
require "open3"
require "pathname"
require "rbconfig"
require "tmpdir"

SOURCE_ROOT = File.expand_path("../..", __dir__)
FIXTURE = File.join(SOURCE_ROOT, ".github/fixtures/profiles/script-assisted")
VALIDATOR = File.join(SOURCE_ROOT, ".github/scripts/validate-skill-repository.rb")
FAILURES = []

def capture(*command, chdir:, env: {})
  Open3.capture3(env, *command, chdir: chdir)
end

def run!(*command, chdir:, env: {})
  stdout, stderr, status = capture(*command, chdir: chdir, env: env)
  return stdout if status.success?

  raise "command failed: #{command.inspect}; status=#{status.exitstatus.inspect}; " \
        "stdout=#{stdout.inspect}; stderr=#{stderr.inspect}"
end

def tree_snapshot(root)
  root_path = Pathname.new(root)
  Find.find(root).sort.each_with_object({}) do |path, snapshot|
    next if path == root

    relative = Pathname.new(path).relative_path_from(root_path).to_s
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
    record = [type, stat.mode & 0o777, stat.mtime.to_r]
    record << File.binread(path) if stat.file?
    record << File.readlink(path) if stat.symlink?
    snapshot[relative] = record
  end
end

def git_index_bytes(repository)
  index_path = run!("git", "rev-parse", "--git-path", "index", chdir: repository).strip
  index_path = File.expand_path(index_path, repository) unless Pathname.new(index_path).absolute?
  File.binread(index_path)
end

def expect_unchanged(label, target, expected_tree, parent, expected_index)
  actual_tree = tree_snapshot(target)
  FAILURES << "#{label}: installed skill tree changed" unless actual_tree == expected_tree
  actual_index = git_index_bytes(parent)
  FAILURES << "#{label}: parent Git index changed" unless actual_index == expected_index
end

def validate(target, outside)
  capture(
    RbConfig.ruby,
    VALIDATOR,
    target,
    chdir: outside,
    env: { "RUBYOPT" => nil }
  )
end

Dir.mktmpdir("non-mutating-consumption") do |workspace|
  outside = File.join(workspace, "outside")
  parent = File.join(workspace, "parent-project")
  skill_prefix = ".agents/skills/line-normalization-helper"
  target = File.join(parent, skill_prefix)
  input_path = File.join(workspace, "input.txt")
  output_path = File.join(workspace, "output.txt")
  invalid_input = File.join(workspace, "invalid.bin")
  invalid_output = File.join(workspace, "invalid-output.txt")

  FileUtils.mkdir_p([outside, target])
  FileUtils.cp_r("#{FIXTURE}/.", target, preserve: true)

  run!("git", "init", "--quiet", chdir: parent)
  run!("git", "config", "user.name", "Non-mutating Consumption Fixture", chdir: parent)
  run!("git", "config", "user.email", "fixture@example.invalid", chdir: parent)
  File.write(File.join(parent, "README.md"), "# Parent project\n", encoding: "UTF-8")
  run!("git", "add", ".", chdir: parent)
  run!("git", "commit", "--quiet", "-m", "Install concrete skill", chdir: parent)

  baseline_tree = tree_snapshot(target)
  baseline_index = git_index_bytes(parent)

  stdout, stderr, status = validate(target, outside)
  unless status.success? && stderr.empty? &&
         stdout.include?("Agent Skill repository structure and profile contracts are valid.")
    FAILURES << "successful validation failed: status=#{status.exitstatus.inspect}, " \
                "stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
  end
  expect_unchanged("successful validation", target, baseline_tree, parent, baseline_index)

  File.binwrite(input_path, "alpha  \r\nbeta\t\r\n")
  input_before = File.binread(input_path)
  stdout, stderr, status = capture(
    RbConfig.ruby,
    "scripts/normalize.rb",
    input_path,
    output_path,
    chdir: target,
    env: { "RUBYOPT" => nil }
  )
  output = File.binread(output_path) if File.file?(output_path)
  unless status.success? && stdout == "#{output_path}\n" && stderr.empty? &&
         output == "alpha\nbeta\n" && File.binread(input_path) == input_before
    FAILURES << "successful helper execution failed: status=#{status.exitstatus.inspect}, " \
                "stdout=#{stdout.inspect}, stderr=#{stderr.inspect}, output=#{output.inspect}"
  end
  expect_unchanged("successful helper execution", target, baseline_tree, parent, baseline_index)

  File.binwrite(invalid_input, "\xFF".b)
  invalid_input_before = File.binread(invalid_input)
  stdout, stderr, status = capture(
    RbConfig.ruby,
    "scripts/normalize.rb",
    invalid_input,
    invalid_output,
    chdir: target,
    env: { "RUBYOPT" => nil }
  )
  invalid_input_unchanged = File.file?(invalid_input) &&
                            File.binread(invalid_input) == invalid_input_before
  unless status.exitstatus == 3 && stdout.empty? && stderr.include?("invalid UTF-8 input") &&
         !File.exist?(invalid_output) && invalid_input_unchanged
    FAILURES << "failed helper execution did not preserve its boundary: " \
                "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, " \
                "stderr=#{stderr.inspect}, input_unchanged=#{invalid_input_unchanged}"
  end
  expect_unchanged("failed helper execution", target, baseline_tree, parent, baseline_index)

  parent_head = run!("git", "rev-parse", "HEAD", chdir: parent).strip
  gitlink_path = File.join(skill_prefix, "scripts", "index-only-link")
  run!(
    "git", "update-index", "--add", "--cacheinfo",
    "160000,#{parent_head},#{gitlink_path}",
    chdir: parent
  )
  gitlink_index = git_index_bytes(parent)
  FAILURES << "index-only gitlink unexpectedly exists on the filesystem" \
    if File.exist?(File.join(parent, gitlink_path))

  _stdout, stderr, status = validate(target, outside)
  diagnostic = "Operational resource gitlinks are not allowed: scripts/index-only-link"
  if status.success?
    FAILURES << "expected validation failure for index-only gitlink"
  elsif !stderr.include?(diagnostic)
    FAILURES << "expected diagnostic #{diagnostic.inspect}; stderr=#{stderr.inspect}"
  end
  expect_unchanged("failed validation", target, baseline_tree, parent, gitlink_index)
end

unless FAILURES.empty?
  FAILURES.each { |failure| warn failure }
  exit 1
end

puts "Non-mutating skill consumption smoke tests passed."
