# frozen_string_literal: true

require "find"
require "yaml"

module ProfileContracts
  class ParseError < StandardError; end

  module ValuePolicy
    module_function

    def strip_backticks(value)
      normalized = value.to_s.strip
      if normalized.length >= 2 && normalized.start_with?("`") && normalized.end_with?("`")
        normalized[1...-1]
      else
        normalized
      end
    end

    def unresolved_scalar?(value)
      normalized = strip_backticks(value).gsub(/\s+/, " ").strip
      return false if normalized.empty?

      marker = /\A(?:TBD|FIXME|PLACEHOLDER)\.?\z/i
      phrase = /\A(?:(?:details?|behavior|contract|implementation|documentation)\s+(?:forthcoming|pending|to\s+follow)|to\s+be\s+(?:added|decided|determined|defined|documented|specified)|will\s+be\s+(?:added|defined|documented|specified)(?:\s+later)?)\.?\z/i
      marker.match?(normalized) || phrase.match?(normalized)
    end

    def resolved?(value)
      value && !value.to_s.strip.empty? &&
        !/\b(?:TODO|UNSELECTED)\b/i.match?(value.to_s) &&
        !unresolved_scalar?(value)
    end

    def concrete?(value)
      resolved?(value) && !/\A(?:NONE|NOT\s+(?:SUPPORTED|APPLICABLE))\z/i.match?(strip_backticks(value))
    end

    def resolved_allow_not_supported?(value)
      resolved?(value) && !/\A(?:NONE|NOT\s+APPLICABLE)\z/i.match?(strip_backticks(value))
    end
  end

  ScalarEntry = Struct.new(:line_number, :kind, :label, :value, keyword_init: true)
  Declaration = Struct.new(:path, :line_number, :fields, keyword_init: true)

  class MarkdownDocument
    attr_reader :path, :text

    def self.read(path)
      new(File.read(path), path: path)
    end

    def initialize(text, path: nil)
      @text = text.to_s
      @path = path
    end

    def lines
      @lines ||= text.lines(chomp: true)
    end

    def section(heading)
      level = heading[/\A#+/].length
      boundary = level == 2 ? "^##\\s|\\z" : "^(?:##|###)\\s|\\z"
      match = text.match(
        Regexp.new("^#{Regexp.escape(heading)}\\s*$\\n(.*?)(?=#{boundary})", Regexp::MULTILINE)
      )
      match && match[1]
    end

    def field(label, section: text)
      match = section.to_s.match(/^#{Regexp.escape(label)}:\s*(.*?)\s*$/)
      match && ValuePolicy.strip_backticks(match[1])
    end

    def list_field(label, section: text)
      match = section.to_s.match(/^\s*-\s*#{Regexp.escape(label)}:\s*(.*?)\s*$/)
      match && ValuePolicy.strip_backticks(match[1])
    end

    def summary_values(label)
      lines.filter_map do |raw_line|
        normalized = normalize_summary_line(raw_line)
        match = normalized.match(/\A#{Regexp.escape(label)}:\s*(.*?)\s*\z/)
        ValuePolicy.strip_backticks(match[1]) if match
      end
    end

    def table_rows(section = text)
      section.to_s.lines.filter_map do |raw_line|
        cells = parse_table_cells(raw_line.strip)
        next unless cells
        next if cells.empty?
        next if cells.all? { |cell| /\A:?-+:?\z/.match?(cell) }

        cells.map { |cell| ValuePolicy.strip_backticks(cell) }
      end
    end

    def table_value(item, section: text)
      row = table_rows(section).find { |cells| cells.first == item }
      row && row.length == 2 ? row[1] : nil
    end

    def support_values
      text.scan(/^Supported:\s*(.*?)\s*$/).flatten.map { |value| ValuePolicy.strip_backticks(value) }
    end

    def declarations(label)
      results = []
      current = nil

      lines.each_with_index do |raw_line, index|
        normalized = normalize_summary_line(raw_line)
        if (match = normalized.match(/\A#{Regexp.escape(label)}:\s*(.+?)\s*\z/))
          current = Declaration.new(
            path: ValuePolicy.strip_backticks(match[1]),
            line_number: index + 1,
            fields: {}
          )
          results << current
          next
        end

        next unless current

        if normalized.start_with?("#") || normalized == "```"
          current = nil
          next
        end

        if (match = normalized.match(/\A([^:]+):\s*(.*?)\s*\z/))
          current.fields[match[1].strip] = ValuePolicy.strip_backticks(match[2])
        end
      end

      results
    end

    def each_scalar
      return enum_for(__method__) unless block_given?

      lines.each_with_index do |raw_line, index|
        normalized = raw_line.strip
        next if normalized.empty? || normalized.match?(/\A```/)

        line_number = index + 1
        yield ScalarEntry.new(line_number: line_number, kind: :line, value: normalized)

        field_match = normalized.match(/\A(?:[-*]\s+)?([^|#`][^:]{0,120}?):\s*(.*?)\s*\z/)
        if field_match
          yield ScalarEntry.new(
            line_number: line_number,
            kind: :field,
            label: field_match[1].strip,
            value: field_match[2]
          )
        end

        cells = parse_table_cells(normalized)
        next unless cells
        next if cells.empty?
        next if cells.all? { |cell| /\A:?-+:?\z/.match?(cell) }

        cells.each do |cell|
          yield ScalarEntry.new(line_number: line_number, kind: :table, value: cell)
        end
      end
    end

    private

    def normalize_summary_line(line)
      normalized = line.strip
      normalized = normalized[2..].strip if normalized.start_with?("- ")
      normalized
    end

    def parse_table_cells(line)
      return nil unless line.start_with?("|") && line.end_with?("|")

      cells = []
      current = +""
      escaped = false

      line[1...-1].each_char do |character|
        if character == "|" && !escaped
          cells << current.strip
          current = +""
        else
          current << character
        end

        if character == "\\"
          escaped = !escaped
        else
          escaped = false
        end
      end
      cells << current.strip
      cells
    end
  end

  class SkillDocument < MarkdownDocument
    attr_reader :metadata

    def self.read(path = "SKILL.md")
      unless File.file?(path)
        raise ParseError, "Missing universally required file: #{path}"
      end

      new(File.read(path), path: path)
    end

    def initialize(text, path: nil)
      super
      @metadata = parse_frontmatter
    end

    private

    def parse_frontmatter
      unless lines.first == "---"
        raise ParseError, "#{path || 'SKILL.md'} must begin with YAML frontmatter."
      end

      closing_index = (1...lines.length).find { |index| lines[index] == "---" }
      unless closing_index
        raise ParseError, "#{path || 'SKILL.md'} YAML frontmatter must have a closing --- delimiter."
      end

      value = YAML.safe_load(
        lines[1...closing_index].join("\n"),
        permitted_classes: [],
        permitted_symbols: [],
        aliases: false
      )
      unless value.is_a?(Hash)
        raise ParseError, "#{path || 'SKILL.md'} YAML frontmatter must be a mapping."
      end

      value
    rescue Psych::Exception => e
      raise ParseError, "#{path || 'SKILL.md'} YAML frontmatter is invalid: #{e.message}"
    end
  end

  class ProfileSelection
    attr_reader :path, :profiles

    def self.load(path = "SKILL.md", document: nil)
      document ||= SkillDocument.read(path)
      declarations = document.summary_values("Selected profiles")
      unless declarations.length == 1
        raise ParseError, "#{path} must contain exactly one 'Selected profiles:' declaration."
      end

      profiles = declarations.first.split(",").map(&:strip).reject(&:empty?)
      if profiles.empty?
        raise ParseError, "#{path} 'Selected profiles:' must contain at least one non-empty profile tag."
      end

      new(path, profiles)
    end

    def initialize(path, profiles)
      @path = path
      @profiles = profiles.freeze
    end

    def template_scaffold?
      profiles == ["template-scaffold"]
    end

    def selected?(profile)
      profiles.include?(profile)
    end
  end

  class RepositorySnapshot
    GUIDANCE_ARTIFACT_EXTENSIONS = %w[.md .markdown .mdx .rst .adoc .asciidoc .txt .pdf].freeze
    GUIDANCE_ARTIFACT_NAMES = %w[
      README README.md README.markdown README.rst NOTES NOTES.md
      ARCHITECTURE ARCHITECTURE.md CONTRIBUTING CONTRIBUTING.md
    ].freeze

    attr_reader :root

    def initialize(root = ".")
      @root = File.expand_path(root)
    end

    def file?(path)
      File.file?(absolute(path))
    end

    def symlink?(path)
      File.symlink?(absolute(path))
    end

    def directory?(path)
      File.directory?(absolute(path))
    end

    def document(path)
      return nil unless file?(path)

      MarkdownDocument.read(absolute(path))
    end

    def operational_file_present?(directory)
      absolute_directory = absolute(directory)
      return false unless File.directory?(absolute_directory) && !File.symlink?(absolute_directory)

      Find.find(absolute_directory).any? do |path|
        next false if path == absolute_directory || File.directory?(path)

        relative = path.delete_prefix("#{root}/")
        relative != "#{directory}/README.md"
      end
    end

    def code_artifact_present?(directory)
      absolute_directory = absolute(directory)
      return false unless File.directory?(absolute_directory) && !File.symlink?(absolute_directory)

      Find.find(absolute_directory).any? do |path|
        next false if path == absolute_directory || File.directory?(path)
        next false unless File.file?(path) && !File.symlink?(path)

        basename = File.basename(path)
        extension = File.extname(path).downcase
        next false if GUIDANCE_ARTIFACT_NAMES.any? { |name| basename.casecmp?(name) }
        next false if GUIDANCE_ARTIFACT_EXTENSIONS.include?(extension)

        true
      end
    end

    def root_files
      Dir.children(root).select { |path| File.file?(absolute(path)) && !File.symlink?(absolute(path)) }
    end

    private

    def absolute(path)
      File.join(root, path)
    end
  end

  module_function

  def support_token(value)
    ValuePolicy.strip_backticks(value).split(/[;\s]/).first&.upcase
  end
end
