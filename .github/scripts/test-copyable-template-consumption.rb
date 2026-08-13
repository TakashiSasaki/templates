#!/usr/bin/env ruby
# frozen_string_literal: true

require "digest"
require "fileutils"
require "find"
require "open3"
require "pathname"
require "rbconfig"
require "tmpdir"

SOURCE_ROOT = File.expand_path("../..", __dir__)
TEMPLATE_ROOT = File.join(SOURCE_ROOT, "template")
DISTRIBUTION_VALIDATOR = File.join(SOURCE_ROOT, ".github/scripts/validate-skill-distribution.rb")
ENGINE_PATHS = {
  ".github/scripts/test-template-adoption.rb" => "Template adoption smoke tests passed.",
  ".github/scripts/test-installation-modes.rb" => "Installation mode smoke tests passed."
}.freeze
ENGINE_REWRITES = {
  ".github/scripts/test-template-adoption.rb" => {
    ".github/scripts/validate-skill-repository.rb" => ".github/scripts/validate_skill_repository.py",
    "command = [RbConfig.ruby, VALIDATOR]" => "command = [ENV.fetch(\"PYTHON\", \"python\"), VALIDATOR]"
  },
  ".github/scripts/test-installation-modes.rb" => {
    ".github/scripts/validate-skill-repository.rb" => ".github/scripts/validate_skill_repository.py",
    "    RbConfig.ruby,\n    VALIDATOR," => "    ENV.fetch(\"PYTHON\", \"python\"),\n    VALIDATOR,"
  }
}.freeze
SOURCE_ONLY_PATHS = %w[
  CHANGELOG.md
  CONTRIBUTING.md
  distribution-manifest.json
  docs/publication-catalog.json
  docs/publication-maintenance.md
  docs/architecture/distribution-boundary.md
  docs/architecture/distribution-classification.json
  .github/REVIEW_GUIDELINES.md
  .github/fixtures
  .github/workflows/pages.yml
  .github/workflows/validate-structure.yml
  .github/workflows/validate-portable-consumption.yml
  .github/workflows/validate-extended-profile-contracts.yml
].freeze
GIT_ENV = {
  "GIT_DIR" => nil,
  "GIT_INDEX_FILE" => nil,
  "GIT_WORK_TREE" => nil,
  "RUBYOPT" => nil
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
    record = [type, stat.mode & 0o7777]
    record << Digest::SHA256.file(path).hexdigest if stat.file?
    record << File.readlink(path) if stat.symlink?
    snapshot[relative] = record
  end
end

def copy_template(target)
  FileUtils.mkdir_p(target)
  FileUtils.cp_r("#{TEMPLATE_ROOT}/.", target, preserve: true)
end

def adapt_engine_for_python(relative, path)
  content = File.read(path, encoding: "UTF-8")
  ENGINE_REWRITES.fetch(relative).each do |before, after|
    unless content.include?(before)
      raise "Python engine rewrite source is missing in #{relative}: #{before.inspect}"
    end

    content = content.sub(before, after)
  end
  File.write(path, content, encoding: "UTF-8")
end

def run_engine(path, root)
  Open3.capture3(GIT_ENV, RbConfig.ruby, path, chdir: root)
end

unless File.directory?(TEMPLATE_ROOT) && File.file?(File.join(TEMPLATE_ROOT, "SKILL.md"))
  warn "copyable template root is missing or incomplete: #{TEMPLATE_ROOT}"
  exit 1
end

source_before = tree_snapshot(TEMPLATE_ROOT)
stdout, stderr, status = Open3.capture3(
  GIT_ENV,
  RbConfig.ruby,
  DISTRIBUTION_VALIDATOR,
  SOURCE_ROOT,
  chdir: SOURCE_ROOT
)
unless status.success? && stderr.empty? && stdout.include?("Skill template distribution is valid.")
  failures << "canonical distribution validation failed: status=#{status.exitstatus.inspect}, " \
              "stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
end

Dir.mktmpdir("copyable-template-consumption") do |workspace|
  clean_source = File.join(workspace, "canonical template source with spaces", "日本語")
  copy_template(clean_source)

  copied_before_injection = tree_snapshot(clean_source)
  unless copied_before_injection == source_before
    failures << "clean-room copy differs from template/ bytes, modes, paths, or link types"
  end

  failures << "copy retained an unexpected template/ wrapper" if Dir.exist?(File.join(clean_source, "template"))
  failures << "SKILL.md is not directly under the copied root" unless File.file?(File.join(clean_source, "SKILL.md"))

  SOURCE_ONLY_PATHS.each do |relative|
    path = File.join(clean_source, relative)
    failures << "source-only path leaked into copyable template: #{relative}" if File.exist?(path) || File.symlink?(path)
  end

  ENGINE_PATHS.each_key do |relative|
    source = File.join(SOURCE_ROOT, relative)
    destination = File.join(clean_source, relative)
    unless File.file?(source) && !File.symlink?(source)
      failures << "missing source-owned consumption engine: #{relative}"
      next
    end
    FileUtils.mkdir_p(File.dirname(destination))
    FileUtils.cp(source, destination, preserve: true)
    begin
      adapt_engine_for_python(relative, destination)
    rescue StandardError => e
      failures << e.message
    end
  end

  ENGINE_PATHS.each do |relative, success_line|
    engine = File.join(clean_source, relative)
    next unless File.file?(engine)

    stdout, stderr, status = run_engine(engine, clean_source)
    unless status.success? && stderr.empty? && stdout.lines.last&.strip == success_line
      failures << "#{relative} failed from the clean-room template copy: " \
                  "status=#{status.exitstatus.inspect}, stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
    end
  end
end

source_after = tree_snapshot(TEMPLATE_ROOT)
failures << "consumption validation mutated template/" unless source_after == source_before

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Copyable template adoption and installation tests passed."
