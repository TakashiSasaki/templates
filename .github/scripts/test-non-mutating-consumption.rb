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

def tree_snapshot(root, exclude: [])
  root_path = Pathname.new(root)
  excluded_roots = exclude.map { |relative| File.expand_path(relative, root) }
  paths = []

  Find.find(root) do |path|
    excluded = path != root && excluded_roots.any? do |excluded_root|
      path == excluded_root || path.start_with?("#{excluded_root}#{File::SEPARATOR}")
    end
    if excluded
      Find.prune if File.directory?(path)
      next
    end
    paths << path
  end

  paths.sort.each_with_object({}) do |path, snapshot|
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

def context_snapshot(target, parent, outside)
  {
    skill: tree_snapshot(target),
    parent: tree_snapshot(parent, exclude: [".git"]),
    outside: tree_snapshot(outside),
    index: git_index_bytes(parent)
  }
end

def expect_context_unchanged(label, target, parent, outside, expected)
  actual = context_snapshot(target, parent, outside)
  FAILURES << "#{label}: installed skill tree changed" unless actual[:skill] == expected[:skill]
  FAILURES << "#{label}: parent worktree changed outside .git" \
    unless actual[:parent] == expected[:parent]
  FAILURES << "#{label}: unrelated working directory changed" \
    unless actual[:outside] == expected[:outside]
  FAILURES << "#{label}: parent Git index changed" unless actual[:index] == expected[:index]
end

def expect_only_declared_output(label, root, before, output_relative, expected_bytes)
  after = tree_snapshot(root)
  unless after.keys == before.keys
    FAILURES << "#{label}: caller-owned inventory changed: " \
                "before=#{before.keys.inspect}, after=#{after.keys.inspect}"
    return
  end

  before.each do |relative, record|
    next if relative == output_relative

    if relative == "."
      FAILURES << "#{label}: caller-owned root type or permissions changed" \
        unless after[relative][0, 2] == record[0, 2]
    elsif after[relative] != record
      FAILURES << "#{label}: caller-owned entry changed: #{relative}"
    end
  end

  output_after = after.fetch(output_relative)
  output_valid = output_after[0] == "file" && output_after[3] == expected_bytes
  FAILURES << "#{label}: declared output did not match its contract" unless output_valid
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

def run_helper(target, input_path, output_path)
  capture(
    RbConfig.ruby,
    "scripts/normalize.rb",
    input_path,
    output_path,
    chdir: target,
    env: { "RUBYOPT" => nil }
  )
end

def expect_alias_rejection(label, target, input_path, output_path, area, expected_context,
                           parent, outside)
  area_before = tree_snapshot(area)
  stdout, stderr, status = run_helper(target, input_path, output_path)
  area_after = tree_snapshot(area)
  diagnostic = "input and output must refer to different files"
  unless status.exitstatus == 2 && stdout.empty? && stderr.include?(diagnostic) &&
         area_after == area_before
    FAILURES << "#{label}: aliased paths were not rejected without mutation: " \
                "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, " \
                "stderr=#{stderr.inspect}, area_unchanged=#{area_after == area_before}"
  end
  expect_context_unchanged(label, target, parent, outside, expected_context)
end

Dir.mktmpdir("non-mutating-consumption") do |workspace|
  outside = File.join(workspace, "outside")
  parent = File.join(workspace, "parent-project")
  caller_root = File.join(workspace, "caller-owned")
  success_area = File.join(caller_root, "success")
  failure_area = File.join(caller_root, "failure")
  same_alias_area = File.join(caller_root, "same-path-alias")
  hard_alias_area = File.join(caller_root, "hard-link-alias")
  skill_prefix = ".agents/skills/line-normalization-helper"
  target = File.join(parent, skill_prefix)
  input_path = File.join(success_area, "input.txt")
  output_path = File.join(success_area, "output.txt")
  invalid_input = File.join(failure_area, "invalid.bin")
  invalid_output = File.join(failure_area, "invalid-output.txt")
  same_path = File.join(same_alias_area, "same.txt")
  hard_input = File.join(hard_alias_area, "input.txt")
  hard_output = File.join(hard_alias_area, "output.txt")

  FileUtils.mkdir_p([
    outside,
    target,
    success_area,
    failure_area,
    same_alias_area,
    hard_alias_area
  ])
  FileUtils.cp_r("#{FIXTURE}/.", target, preserve: true)

  run!("git", "init", "--quiet", chdir: parent)
  run!("git", "config", "user.name", "Non-mutating Consumption Fixture", chdir: parent)
  run!("git", "config", "user.email", "fixture@example.invalid", chdir: parent)
  File.write(File.join(parent, "README.md"), "# Parent project\n", encoding: "UTF-8")
  run!("git", "add", ".", chdir: parent)
  run!("git", "commit", "--quiet", "-m", "Install concrete skill", chdir: parent)

  baseline = context_snapshot(target, parent, outside)

  stdout, stderr, status = validate(target, outside)
  unless status.success? && stderr.empty? &&
         stdout.include?("Agent Skill repository structure and profile contracts are valid.")
    FAILURES << "successful validation failed: status=#{status.exitstatus.inspect}, " \
                "stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
  end
  expect_context_unchanged("successful validation", target, parent, outside, baseline)

  File.binwrite(input_path, "alpha  \r\nbeta\t\r\n")
  File.binwrite(output_path, "stale output\n")
  success_before = tree_snapshot(success_area)
  stdout, stderr, status = run_helper(target, input_path, output_path)
  output = File.binread(output_path) if File.file?(output_path)
  unless status.success? && stdout == "#{output_path}\n" && stderr.empty? &&
         output == "alpha\nbeta\n"
    FAILURES << "successful helper execution failed: status=#{status.exitstatus.inspect}, " \
                "stdout=#{stdout.inspect}, stderr=#{stderr.inspect}, output=#{output.inspect}"
  end
  expect_only_declared_output(
    "successful helper execution",
    success_area,
    success_before,
    "output.txt",
    "alpha\nbeta\n"
  )
  expect_context_unchanged("successful helper execution", target, parent, outside, baseline)

  File.binwrite(invalid_input, "\xFF".b)
  failure_before = tree_snapshot(failure_area)
  stdout, stderr, status = run_helper(target, invalid_input, invalid_output)
  failure_after = tree_snapshot(failure_area)
  unless status.exitstatus == 3 && stdout.empty? && stderr.include?("invalid UTF-8 input") &&
         !File.exist?(invalid_output) && failure_after == failure_before
    FAILURES << "failed helper execution did not preserve its boundary: " \
                "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, " \
                "stderr=#{stderr.inspect}, caller_area_unchanged=#{failure_after == failure_before}"
  end
  expect_context_unchanged("failed helper execution", target, parent, outside, baseline)

  File.binwrite(same_path, "same-path input\r\n")
  expect_alias_rejection(
    "same-path helper rejection",
    target,
    same_path,
    same_path,
    same_alias_area,
    baseline,
    parent,
    outside
  )

  File.binwrite(hard_input, "hard-link input\r\n")
  File.link(hard_input, hard_output)
  FAILURES << "hard-link alias fixture does not identify the same file" \
    unless File.identical?(hard_input, hard_output)
  expect_alias_rejection(
    "hard-link helper rejection",
    target,
    hard_input,
    hard_output,
    hard_alias_area,
    baseline,
    parent,
    outside
  )

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
  expect_context_unchanged(
    "failed validation",
    target,
    parent,
    outside,
    baseline.merge(index: gitlink_index)
  )
end

unless FAILURES.empty?
  FAILURES.each { |failure| warn failure }
  exit 1
end

puts "Non-mutating skill consumption smoke tests passed."
