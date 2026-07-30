#!/usr/bin/env ruby
# frozen_string_literal: true

SKILL_PATH = "SKILL.md"
CLI_PATH = "CLI_INTERFACE.md"

unless File.file?(SKILL_PATH)
  warn "Missing universally required file: SKILL.md"
  exit 1
end

strip_backticks = lambda do |value|
  normalized = value.to_s.strip
  if normalized.length >= 2 && normalized.start_with?("`") && normalized.end_with?("`")
    normalized[1...-1]
  else
    normalized
  end
end

resolved_value = lambda do |value|
  value && !value.strip.empty? && !/\b(?:TODO|UNSELECTED)\b/i.match?(value)
end

markdown_section = lambda do |document, heading|
  level = heading[/\A#+/].length
  boundary = level == 2 ? "^##\\s|\\z" : "^(?:##|###)\\s|\\z"
  match = document.match(
    Regexp.new("^#{Regexp.escape(heading)}\\s*$\\n(.*?)(?=#{boundary})", Regexp::MULTILINE)
  )
  match && match[1]
end

profile_values = File.readlines(SKILL_PATH, chomp: true).filter_map do |raw_line|
  normalized = raw_line.strip
  normalized = normalized[2..].strip if normalized.start_with?("- ")
  match = normalized.match(/\ASelected profiles:\s*(.+?)\s*\z/)
  strip_backticks.call(match[1]) if match
end

if profile_values.length != 1
  warn "SKILL.md must contain exactly one 'Selected profiles:' declaration."
  exit 1
end

selected_profiles = profile_values.first.split(",").map(&:strip).reject(&:empty?)
if selected_profiles == ["template-scaffold"] || !selected_profiles.include?("packaged-cli")
  puts "CLI exit-code contract is not activated."
  exit 0
end

errors = []

unless File.file?(CLI_PATH)
  errors << "Selected profile 'packaged-cli' requires contract file: #{CLI_PATH}"
else
  cli = File.read(CLI_PATH)
  section = markdown_section.call(cli, "### Exit codes")

  if section.nil? || section.strip.empty?
    errors << "#{CLI_PATH} requires a non-empty '### Exit codes' section."
  else
    rows = section.scan(/^\|\s*(-?\d+)\s*\|\s*(.*?)\s*\|\s*$/).map do |code, meaning|
      [Integer(code, 10), strip_backticks.call(meaning)]
    end

    if rows.empty?
      errors << "#{CLI_PATH} requires an integer exit-code mapping table."
    else
      codes = rows.map(&:first)
      duplicates = codes.tally.select { |_code, count| count > 1 }.keys
      unless duplicates.empty?
        errors << "#{CLI_PATH} exit codes must be unique; duplicated: #{duplicates.sort.join(', ')}."
      end

      unless codes.include?(0)
        errors << "#{CLI_PATH} exit-code mapping must include code 0 for successful execution."
      end

      if codes.uniq.length < 5
        errors << "#{CLI_PATH} must map at least five distinct exit codes covering success and distinct failure classes."
      end

      rows.each do |code, meaning|
        unless resolved_value.call(meaning)
          errors << "#{CLI_PATH} exit code #{code} requires a resolved meaning."
        end
      end
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "CLI exit-code contract is valid."
