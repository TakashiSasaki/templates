#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require "rbconfig"
require "tmpdir"

skill_root = File.expand_path("..", __dir__)
helper = File.join(skill_root, "scripts/normalize.rb")
failures = []

Dir.mktmpdir("normalize-helper-test") do |directory|
  input_path = File.join(directory, "input.txt")
  output_path = File.join(directory, "output.txt")
  File.binwrite(input_path, "alpha  \r\nbeta\t\r\n")
  input_before = File.binread(input_path)

  stdout, stderr, status = Open3.capture3(
    RbConfig.ruby,
    helper,
    input_path,
    output_path
  )

  unless status.success? && stdout.chomp == output_path && stderr.empty? &&
         File.binread(output_path) == "alpha\nbeta\n" &&
         File.binread(input_path) == input_before
    failures << "normalization failed: status=#{status.exitstatus.inspect}, " \
                "stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
  end

  stdout, stderr, status = Open3.capture3(
    RbConfig.ruby,
    helper,
    input_path,
    input_path
  )
  unless status.exitstatus == 2 && stdout.empty? &&
         stderr.strip == "input and output must refer to different files" &&
         File.binread(input_path) == input_before
    failures << "same-file rejection failed: status=#{status.exitstatus.inspect}, " \
                "stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
  end

  invalid_path = File.join(directory, "invalid.txt")
  invalid_output_path = File.join(directory, "invalid-output.txt")
  File.binwrite(invalid_path, [0xFF].pack("C"))
  stdout, stderr, status = Open3.capture3(
    RbConfig.ruby,
    helper,
    invalid_path,
    invalid_output_path
  )
  unless status.exitstatus == 3 && stdout.empty? &&
         stderr.strip == "invalid UTF-8 input" &&
         !File.exist?(invalid_output_path)
    failures << "invalid UTF-8 rejection failed: status=#{status.exitstatus.inspect}, " \
                "stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Line normalization helper tests passed."
