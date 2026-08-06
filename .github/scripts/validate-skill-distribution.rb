#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "open3"
require "pathname"
require "set"

module SkillDistribution
  class ValidationError < StandardError; end

  MANIFEST_KEYS = Set.new(%w[
    schema_version
    source_root
    destination_root
    content_transformation_allowed
    required_top_level_entries
    mirrors
    distribution_owned_files
    forbidden_distribution_paths
  ]).freeze
  MIRROR_KEYS = Set.new(%w[source destination exclude]).freeze

  module_function

  def fail!(message)
    raise ValidationError, message
  end

  def safe_relative_path(value, context, allow_dot: false)
    fail!("#{context}: path must be a non-empty string") unless value.is_a?(String) && !value.empty?
    return value if allow_dot && value == "."
    fail!("#{context}: path is not portable: #{value}") if value.include?("\\") || value.include?(":")

    path = Pathname.new(value)
    clean = path.cleanpath.to_s
    if path.absolute? || clean != value || path.each_filename.any? { |part| part == ".." || part.empty? }
      fail!("#{context}: path must be normalized and relative: #{value}")
    end
    fail!("#{context}: .git path component is prohibited: #{value}") if path.each_filename.any? { |part| part.downcase == ".git" }

    value
  end

  def sorted_path_list(value, context)
    fail!("#{context}: value must be an array") unless value.is_a?(Array)
    paths = value.map { |entry| safe_relative_path(entry, context) }
    fail!("#{context}: paths must be sorted") unless paths == paths.sort
    fail!("#{context}: duplicate path") unless paths.uniq == paths
    paths
  end

  def load_manifest(root)
    path = root.join("distribution-manifest.json")
    value = JSON.parse(path.read(encoding: "UTF-8"))
    fail!("distribution manifest: root must be an object") unless value.is_a?(Hash)
    unknown = value.keys.to_set - MANIFEST_KEYS
    missing = MANIFEST_KEYS - value.keys.to_set
    fail!("distribution manifest: unsupported members: #{unknown.to_a.sort.inspect}") unless unknown.empty?
    fail!("distribution manifest: missing members: #{missing.to_a.sort.inspect}") unless missing.empty?
    value
  rescue Errno::ENOENT, Errno::EACCES, JSON::ParserError => e
    fail!("distribution manifest: cannot read valid JSON: #{e.message}")
  end

  def tracked_entries(root)
    stdout, stderr, status = Open3.capture3(
      { "LC_ALL" => "C", "GIT_DIR" => nil, "GIT_WORK_TREE" => nil, "GIT_INDEX_FILE" => nil },
      "git", "-C", root.to_s, "ls-files", "--stage", "-z"
    )
    fail!("distribution validation requires a Git checkout: #{stderr.strip}") unless status.success?

    entries = {}
    stdout.split("\0").each do |record|
      next if record.empty?
      metadata, path = record.split("\t", 2)
      fail!("tracked entry has an invalid index record") unless metadata && path
      mode, _sha, stage = metadata.split(" ", 3)
      fail!("tracked entry uses a nonzero index stage: #{path}") unless stage == "0"
      safe_relative_path(path, "tracked file")
      fail!("tracked path appears more than once: #{path}") if entries.key?(path)
      entries[path] = mode
    end
    entries
  rescue Errno::ENOENT => e
    fail!("distribution validation requires Git: #{e.message}")
  end

  def descendant?(path, prefix)
    path == prefix || path.start_with?("#{prefix}/")
  end

  def mapped_destination(destination, relative)
    relative.empty? ? destination : "#{destination}/#{relative}"
  end

  def validate(root_path = Dir.pwd)
    root = Pathname.new(File.expand_path(root_path))
    fail!("source root is not a directory: #{root}") unless root.directory?

    manifest = load_manifest(root)
    schema_version = manifest["schema_version"]
    fail!("distribution manifest: schema_version must be integer 1") unless schema_version == 1 && schema_version.is_a?(Integer)

    source_root = safe_relative_path(manifest["source_root"], "distribution manifest source_root")
    destination_root = safe_relative_path(manifest["destination_root"], "distribution manifest destination_root", allow_dot: true)
    fail!("distribution manifest: source_root must be template") unless source_root == "template"
    fail!("distribution manifest: destination_root must be .") unless destination_root == "."
    fail!("distribution manifest: content transformation must remain disabled") unless manifest["content_transformation_allowed"] == false

    required_top_level = sorted_path_list(manifest["required_top_level_entries"], "distribution manifest required_top_level_entries")
    distribution_owned = sorted_path_list(manifest["distribution_owned_files"], "distribution manifest distribution_owned_files")
    forbidden = sorted_path_list(manifest["forbidden_distribution_paths"], "distribution manifest forbidden_distribution_paths")

    tracked = tracked_entries(root)
    prefix = "#{source_root}/"
    actual = tracked.each_with_object({}) do |(path, mode), result|
      result[path.delete_prefix(prefix)] = mode if path.start_with?(prefix)
    end
    fail!("distribution: template contains no tracked files") if actual.empty?

    missing_on_disk = actual.keys.select { |relative| !root.join(source_root, relative).exist? && !root.join(source_root, relative).symlink? }.sort
    fail!("distribution: declared files are missing: #{missing_on_disk.inspect}") unless missing_on_disk.empty?

    actual.each do |relative, mode|
      path = root.join(source_root, relative)
      if mode == "120000" || path.symlink?
        fail!("distribution: symbolic links are prohibited: #{relative}")
      end
      fail!("distribution: tracked path is not a regular file: #{relative}") unless path.file?
    end

    mirrors = manifest["mirrors"]
    fail!("distribution manifest: mirrors must be a non-empty array") unless mirrors.is_a?(Array) && !mirrors.empty?

    expected = distribution_owned.to_set
    byte_pairs = []
    mirror_sources = Set.new
    mirror_destinations = Set.new

    mirrors.each_with_index do |mirror, index|
      context = "distribution manifest mirrors[#{index}]"
      fail!("#{context}: value must be an object") unless mirror.is_a?(Hash)
      unknown = mirror.keys.to_set - MIRROR_KEYS
      missing = MIRROR_KEYS - mirror.keys.to_set
      unless unknown.empty? && missing.empty?
        fail!("#{context}: invalid members; missing=#{missing.to_a.sort.inspect}, unsupported=#{unknown.to_a.sort.inspect}")
      end

      source = safe_relative_path(mirror["source"], "#{context} source")
      destination = safe_relative_path(mirror["destination"], "#{context} destination")
      excludes = sorted_path_list(mirror["exclude"], "#{context} exclude")
      fail!("#{context}: duplicate mirror source #{source}") unless mirror_sources.add?(source)
      fail!("#{context}: duplicate mirror destination #{destination}") unless mirror_destinations.add?(destination)

      source_path = root.join(source)
      fail!("#{context}: source may not be a symbolic link: #{source}") if source_path.symlink?

      members = []
      if tracked.key?(source)
        fail!("#{context}: a file mirror may not declare exclusions") unless excludes.empty?
        members << [source, ""]
      else
        source_prefix = "#{source}/"
        source_members = tracked.keys.select { |path| path.start_with?(source_prefix) }.sort
        fail!("#{context}: source does not exist as a tracked file or directory: #{source}") if source_members.empty?
        available = source_members.map { |path| path.delete_prefix(source_prefix) }.to_set
        absent_excludes = excludes.reject { |path| available.include?(path) }
        fail!("#{context}: exclusions are not tracked: #{absent_excludes.inspect}") unless absent_excludes.empty?
        source_members.each do |path|
          relative = path.delete_prefix(source_prefix)
          members << [path, relative] unless excludes.include?(relative)
        end
      end

      members.each do |source_file, relative|
        source_mode = tracked.fetch(source_file)
        fail!("#{context}: source symbolic links are prohibited: #{source_file}") if source_mode == "120000"
        destination_file = mapped_destination(destination, relative)
        safe_relative_path(destination_file, "#{context} mapped destination")
        fail!("#{context}: distribution destination collision: #{destination_file}") if expected.include?(destination_file)
        expected << destination_file
        byte_pairs << [source_file, destination_file, source_mode]
      end
    end

    overlap = distribution_owned.select { |path| forbidden.any? { |entry| descendant?(path, entry) } }
    fail!("distribution manifest: owned and forbidden paths overlap: #{overlap.inspect}") unless overlap.empty?

    missing = (expected - actual.keys.to_set).to_a.sort
    undeclared = (actual.keys.to_set - expected).to_a.sort
    fail!("distribution: declared files are missing: #{missing.inspect}") unless missing.empty?
    fail!("distribution: undeclared files are present: #{undeclared.inspect}") unless undeclared.empty?

    present_forbidden = actual.keys.select { |path| forbidden.any? { |entry| descendant?(path, entry) } }.sort
    fail!("distribution: maintainer-only paths are present: #{present_forbidden.inspect}") unless present_forbidden.empty?

    actual_top_level = actual.keys.map { |path| path.split("/", 2).first }.uniq.sort
    unless actual_top_level == required_top_level
      fail!("distribution: top-level inventory differs; expected=#{required_top_level.inspect}, actual=#{actual_top_level.inspect}")
    end

    distribution_owned.each do |relative|
      path = root.join(source_root, relative)
      mode = actual.fetch(relative)
      fail!("distribution-owned file may not be a symbolic link: #{relative}") if mode == "120000" || path.symlink?
      fail!("distribution-owned path is not a regular file: #{relative}") unless path.file?
    end

    byte_pairs.each do |source_file, destination_file, source_mode|
      destination_mode = actual.fetch(destination_file)
      unless source_mode == destination_mode
        fail!("distribution: mirrored mode differs: #{source_file} -> #{destination_file}")
      end
      source_bytes = root.join(source_file).binread
      destination_bytes = root.join(source_root, destination_file).binread
      unless source_bytes == destination_bytes
        fail!("distribution: mirrored bytes differ: #{source_file} -> #{destination_file}")
      end
    end

    puts "Skill template distribution is valid. #{actual.length} files; #{byte_pairs.length} byte-preserving mirrors."
    true
  rescue Errno::ENOENT, Errno::EACCES => e
    fail!("distribution: cannot inspect required file: #{e.message}")
  end
end

if $PROGRAM_NAME == __FILE__
  if ARGV.length > 1
    warn "usage: ruby #{File.basename(__FILE__)} [SOURCE_ROOT]"
    exit 2
  end

  begin
    SkillDistribution.validate(ARGV.first || Dir.pwd)
  rescue SkillDistribution::ValidationError => e
    warn e.message
    exit 1
  end
end
