#!/usr/bin/env ruby
# frozen_string_literal: true

begin
  unless ARGV.length == 2
    warn "usage: ruby scripts/normalize.rb INPUT OUTPUT"
    exit 2
  end

  input_path, output_path = ARGV
  same_path = File.expand_path(input_path) == File.expand_path(output_path)
  same_file = File.exist?(input_path) && File.exist?(output_path) &&
              File.identical?(input_path, output_path)
  if same_path || same_file
    warn "input and output must refer to different files"
    exit 2
  end

  text = File.binread(input_path).force_encoding(Encoding::UTF_8)
  unless text.valid_encoding?
    warn "invalid UTF-8 input"
    exit 3
  end

  normalized = text.gsub("\r\n", "\n").gsub("\r", "\n")
  normalized = normalized.lines.map { |line| line.sub(/[\t ]+(?=\n?\z)/, "") }.join
  normalized = "#{normalized.sub(/\n*\z/, "")}\n"
  File.binwrite(output_path, normalized)
  puts output_path
rescue SystemCallError => e
  warn e.message
  exit 1
end
