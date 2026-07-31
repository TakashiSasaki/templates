#!/usr/bin/env ruby
# frozen_string_literal: true

begin
  unless ARGV.length == 2
    warn "usage: ruby scripts/normalize.rb INPUT OUTPUT"
    exit 2
  end

  input_path, output_path = ARGV
  text = File.read(input_path, encoding: "UTF-8")
  normalized = text.gsub("\r\n", "\n").gsub("\r", "\n")
  normalized = normalized.lines.map { |line| line.sub(/[\t ]+(?=\n?\z)/, "") }.join
  normalized = "#{normalized.sub(/\n*\z/, "")}\n"
  File.write(output_path, normalized, mode: "w", encoding: "UTF-8")
  puts output_path
rescue Encoding::InvalidByteSequenceError, Encoding::UndefinedConversionError => e
  warn "invalid UTF-8 input: #{e.message}"
  exit 3
rescue SystemCallError => e
  warn e.message
  exit 1
end
