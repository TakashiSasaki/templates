#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "lib/profile_contracts"

SKILL_PATH = "SKILL.md"
CLI_PATH = "CLI_INTERFACE.md"
PORTABLE_EXIT_CODE_RANGE = (0..255)

begin
  selection = ProfileContracts::ProfileSelection.load(SKILL_PATH)
rescue ProfileContracts::ParseError => error
  warn error.message
  exit 1
end

if selection.template_scaffold? || !selection.selected?("packaged-cli")
  puts "CLI exit-code contract is not activated."
  exit 0
end

policy = ProfileContracts::ValuePolicy
success_meaning = lambda do |value|
  next false unless policy.concrete?(value)

  normalized = policy.strip_backticks(value).gsub(/\s+/, " ").strip
  negated_success = /\b(?:not|non[-\s]?)\s*(?:success|successful)\b/i
  non_success_outcome = /\b(?:failure|failed|error|invalid|negative|refusal|refused|denied|unsuccessful|timeout|timed\s+out|cancel(?:led|ed)?|aborted|interrupted)\b/i

  !negated_success.match?(normalized) && !non_success_outcome.match?(normalized)
end

errors = []

unless File.file?(CLI_PATH)
  errors << "Selected profile 'packaged-cli' requires contract file: #{CLI_PATH}"
else
  cli = ProfileContracts::MarkdownDocument.read(CLI_PATH)
  section = cli.section("### Exit codes")

  if section.nil? || section.strip.empty?
    errors << "#{CLI_PATH} requires a non-empty '### Exit codes' section."
  else
    table_rows = ProfileContracts::MarkdownDocument.new(section, path: CLI_PATH).table_rows.filter_map do |cells|
      next unless cells.length == 2

      code_text, meaning = cells
      next if code_text.casecmp?("Code") || /\A:?-+:?\z/.match?(code_text)

      [code_text, meaning]
    end

    if table_rows.empty?
      errors << "#{CLI_PATH} requires an exit-code mapping table."
    else
      rows = table_rows.filter_map do |code_text, meaning|
        unless /\A\d+\z/.match?(code_text)
          errors << "#{CLI_PATH} exit code #{code_text.inspect} must be an integer in 0..255."
          next
        end

        code = Integer(code_text, 10)
        unless PORTABLE_EXIT_CODE_RANGE.cover?(code)
          errors << "#{CLI_PATH} exit code #{code} is outside the portable process-status range 0..255."
          next
        end

        [code, meaning]
      end

      codes = rows.map(&:first)
      duplicates = codes.tally.select { |_code, count| count > 1 }.keys
      unless duplicates.empty?
        errors << "#{CLI_PATH} exit codes must be unique; duplicated: #{duplicates.sort.join(', ')}."
      end

      unless codes.include?(0)
        errors << "#{CLI_PATH} exit-code mapping must include code 0 for successful execution."
      end

      unless codes.any? { |code| code != 0 }
        errors << "#{CLI_PATH} exit-code mapping must include at least one nonzero outcome or failure code."
      end

      rows.each do |code, meaning|
        unless policy.concrete?(meaning)
          errors << "#{CLI_PATH} exit code #{code} requires a concrete caller-visible meaning."
        end
      end

      zero_meaning = rows.find { |code, _meaning| code.zero? }&.last
      if zero_meaning && !success_meaning.call(zero_meaning)
        errors << "#{CLI_PATH} exit code 0 must denote normal completion and must not describe a failure, " \
                  "error, invalid input, refusal, negative outcome, timeout, cancellation, or interruption."
      end
    end
  end
end

unless errors.empty?
  errors.uniq.each { |error| warn error }
  exit 1
end

puts "CLI exit-code contract is valid."
