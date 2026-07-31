# frozen_string_literal: true

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
  end

  ScalarEntry = Struct.new(:line_number, :kind, :label, :value, keyword_init: true)

  class MarkdownDocument
    attr_reader :path, :text

    def self.read(path)
      new(File.read(path), path: path)
    end

    def initialize(text, path: nil)
      @text = text.to_s
      @path = path
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

    def summary_values(label)
      text.lines.filter_map do |raw_line|
        normalized = raw_line.strip
        normalized = normalized[2..].strip if normalized.start_with?("- ")
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

    def each_scalar
      return enum_for(__method__) unless block_given?

      text.lines.each_with_index do |raw_line, index|
        normalized = raw_line.strip
        next if normalized.empty? || normalized.match?(/\A```/)

        line_number = index + 1
        yield ScalarEntry.new(
          line_number: line_number,
          kind: :line,
          value: normalized
        )

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
          yield ScalarEntry.new(
            line_number: line_number,
            kind: :table,
            value: cell
          )
        end
      end
    end

    private

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

  class ProfileSelection
    attr_reader :path, :profiles

    def self.load(path = "SKILL.md")
      unless File.file?(path)
        raise ParseError, "Missing universally required file: #{path}"
      end

      document = MarkdownDocument.read(path)
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
end
