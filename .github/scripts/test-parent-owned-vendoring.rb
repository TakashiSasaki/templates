#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "rbconfig"
require "tmpdir"

SOURCE_ROOT = File.expand_path("../..", __dir__)
FIXTURE = File.join(SOURCE_ROOT, ".github/fixtures/profiles/script-assisted")
VALIDATOR = File.join(SOURCE_ROOT, ".github/scripts/validate-skill-repository.rb")
SKILL_FILES = %w[SKILL.md scripts/normalize.rb].freeze
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

def validate(target, outside)
  capture(
    RbConfig.ruby,
    VALIDATOR,
    target,
    chdir: outside,
    env: { "RUBYOPT" => nil }
  )
end

def expect_validation_success(target, outside)
  stdout, stderr, status = validate(target, outside)
  return if status.success? && stderr.empty? &&
            stdout.include?("Agent Skill repository structure and profile contracts are valid.")

  FAILURES << "expected parent-owned vendored skill validation success; " \
              "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
end

def expect_gitlink_rejection(target, outside)
  _stdout, stderr, status = validate(target, outside)
  diagnostic = "Operational resource gitlinks are not allowed: scripts/index-only-link"
  if status.success?
    FAILURES << "expected parent-index gitlink rejection"
  elsif !stderr.include?(diagnostic)
    FAILURES << "expected diagnostic #{diagnostic.inspect}; stderr=#{stderr.inspect}"
  end
end

def git_index_bytes(repository)
  index_path = run!("git", "rev-parse", "--git-path", "index", chdir: repository).strip
  index_path = File.expand_path(index_path, repository) unless index_path.start_with?(File::SEPARATOR)
  File.binread(index_path)
end

def tracked_skill_entries(repository, prefix)
  output = run!("git", "ls-files", "--stage", "--", prefix, chdir: repository)
  output.lines.to_h do |line|
    match = line.match(/\A(\d+)\s+[0-9a-f]+\s+\d+\t(.+)\n?\z/)
    raise "unexpected git ls-files record: #{line.inspect}" unless match

    [match[2], match[1]]
  end
end

def content_map(root)
  SKILL_FILES.to_h { |relative| [relative, File.binread(File.join(root, relative))] }
end

def exercise_helper(target)
  input_path = File.join(target, "input.txt")
  output_path = File.join(target, "output.txt")
  File.binwrite(input_path, "alpha  \r\nbeta\t\r\n")
  before = File.binread(input_path)

  stdout, stderr, status = capture(
    RbConfig.ruby,
    "scripts/normalize.rb",
    "input.txt",
    "output.txt",
    chdir: target
  )
  output = File.binread(output_path) if File.file?(output_path)
  return if status.success? && stdout == "output.txt\n" && stderr.empty? &&
            output == "alpha\nbeta\n" && File.binread(input_path) == before

  FAILURES << "helper execution failed; status=#{status.exitstatus.inspect}, " \
              "stdout=#{stdout.inspect}, stderr=#{stderr.inspect}, output=#{output.inspect}"
end

Dir.mktmpdir("parent-owned-vendoring") do |workspace|
  outside = File.join(workspace, "outside")
  source = File.join(workspace, "concrete-skill-source")
  archive = File.join(workspace, "concrete-skill.tar")
  extracted = File.join(workspace, "archive-extracted")
  parent = File.join(workspace, "parent-project")
  skill_prefix = ".agents/skills/line-normalization-helper"
  target = File.join(parent, skill_prefix)

  FileUtils.mkdir_p([outside, source, extracted, parent])
  FileUtils.cp_r("#{FIXTURE}/.", source, preserve: true)

  run!("git", "init", "--quiet", chdir: source)
  run!("git", "config", "user.name", "Parent-owned Vendoring Fixture", chdir: source)
  run!("git", "config", "user.email", "fixture@example.invalid", chdir: source)
  run!("git", "add", ".", chdir: source)
  run!("git", "commit", "--quiet", "-m", "Create concrete skill", chdir: source)
  run!(
    "git", "archive", "--format=tar", "--prefix=line-normalization-helper/",
    "--output=#{archive}", "HEAD",
    chdir: source
  )
  run!("tar", "-xf", archive, "-C", extracted, chdir: workspace)

  run!("git", "init", "--quiet", chdir: parent)
  run!("git", "config", "user.name", "Parent Project Fixture", chdir: parent)
  run!("git", "config", "user.email", "parent@example.invalid", chdir: parent)
  File.write(File.join(parent, "README.md"), "# Parent project\n", encoding: "UTF-8")
  run!("git", "add", "README.md", chdir: parent)
  run!("git", "commit", "--quiet", "-m", "Create parent project", chdir: parent)

  FileUtils.mkdir_p(target)
  FileUtils.cp_r(
    "#{File.join(extracted, 'line-normalization-helper')}/.",
    target,
    preserve: true
  )
  run!("git", "add", "--", skill_prefix, chdir: parent)
  run!("git", "commit", "--quiet", "-m", "Vendor concrete skill", chdir: parent)

  expected_entries = SKILL_FILES.to_h do |relative|
    [File.join(skill_prefix, relative), "100644"]
  end
  actual_entries = tracked_skill_entries(parent, skill_prefix)
  FAILURES << "parent index does not own the expected regular files: #{actual_entries.inspect}" \
    unless actual_entries == expected_entries

  FAILURES << "vendored bytes differ from the committed source" \
    unless content_map(target) == content_map(source)
  FAILURES << "vendored target unexpectedly contains Git metadata" \
    if File.exist?(File.join(target, ".git"))
  FAILURES << "vendored target retained an archive wrapper" \
    if Dir.exist?(File.join(target, "line-normalization-helper"))

  discovered_root = run!("git", "rev-parse", "--show-toplevel", chdir: target).strip
  FAILURES << "validator target did not discover the parent worktree" \
    unless File.realpath(discovered_root) == File.realpath(parent)

  index_before = git_index_bytes(parent)
  expect_validation_success(target, outside)
  index_after = git_index_bytes(parent)
  FAILURES << "successful validation modified the parent index" unless index_after == index_before
  exercise_helper(target)

  parent_head = run!("git", "rev-parse", "HEAD", chdir: parent).strip
  gitlink_path = File.join(skill_prefix, "scripts", "index-only-link")
  run!(
    "git", "update-index", "--add", "--cacheinfo",
    "160000,#{parent_head},#{gitlink_path}",
    chdir: parent
  )
  FAILURES << "index-only gitlink unexpectedly exists on the filesystem" \
    if File.exist?(File.join(parent, gitlink_path))

  gitlink_index_before = git_index_bytes(parent)
  expect_gitlink_rejection(target, outside)
  gitlink_index_after = git_index_bytes(parent)
  FAILURES << "failed validation modified the parent index" \
    unless gitlink_index_after == gitlink_index_before
end

unless FAILURES.empty?
  FAILURES.each { |failure| warn failure }
  exit 1
end

puts "Parent-owned vendoring smoke tests passed."
