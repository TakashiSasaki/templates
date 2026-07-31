#!/usr/bin/env ruby
# frozen_string_literal: true

begin
  unless ARGV.length == 2
    warn "usage: ruby scripts/normalize.rb INPUT OUTPUT"
    exit 2
  end

  input_path, output_path = ARGV
  text = File.binread(input_path).force_encoding(Encoding::UTF_8)
  unless text.valid_encoding?
    warn "invalid UTF-8 input"
    exit 3
  end

  normalized = text.gsub("\r\n", "\n").gsub("\r", "\n")
  normalized = normalized.lines.map { |line| line.sub(/[\t ]+(?=\n?\z)/, "") }.join
  normalized = "#{normalized.sub(/\n*\z/, "")}\n"
  File.write(output_path, normalized, mode: "w", encoding: "UTF-8")
  puts output_path
rescue SystemCallError => e
  warn e.message
  exit 1
end
