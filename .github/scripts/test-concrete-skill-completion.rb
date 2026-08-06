#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "rbconfig"
require "tmpdir"

SOURCE_ROOT = File.expand_path("../..", __dir__)
FIXTURE = File.join(SOURCE_ROOT, ".github/fixtures/profiles/instruction-only")
VALIDATOR = File.join(SOURCE_ROOT, ".github/scripts/validate-skill-repository.rb")
CANONICAL_LICENSE_PATH = File.join(SOURCE_ROOT, "template", "LICENSE")
LICENSE_TEMPLATE_PATH = File.join(SOURCE_ROOT, "template", "LICENSE.template")
GIT_ENV = {
  "GIT_DIR" => nil,
  "GIT_INDEX_FILE" => nil,
  "GIT_WORK_TREE" => nil,
  "RUBYOPT" => nil
}.freeze
FAILURES = []

EXPECTED_CANONICAL_LICENSE = <<~LICENSE.freeze
  MIT No Attribution

  Copyright 2026 Takashi Sasaki

  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
LICENSE

CANONICAL_TEMPLATE_README = <<~MARKDOWN.freeze
  # Language-neutral Agent Skill Template

  This repository is a template for developing a portable Agent Skill. Its root is intended to become the installable Skill directory directly:
MARKDOWN

CONCRETE_README = <<~MARKDOWN.freeze
  # Evidence summary skill

  This repository contains the completed evidence-summary Agent Skill.
MARKDOWN

def run!(*command, chdir:)
  stdout, stderr, status = Open3.capture3(GIT_ENV, *command, chdir: chdir)
  return stdout if status.success?

  raise "command failed: #{command.inspect}; status=#{status.exitstatus.inspect}; " \
        "stdout=#{stdout.inspect}; stderr=#{stderr.inspect}"
end

def validate(directory)
  Open3.capture3(
    GIT_ENV,
    RbConfig.ruby,
    VALIDATOR,
    directory,
    chdir: SOURCE_ROOT
  )
end

def materialize
  Dir.mktmpdir("concrete-skill-completion") do |directory|
    FileUtils.cp_r("#{FIXTURE}/.", directory, preserve: true)
    run!("git", "init", "--quiet", chdir: directory)
    run!("git", "add", ".", chdir: directory)
    yield directory
  end
end

def expect_success(label)
  materialize do |directory|
    yield directory if block_given?
    stdout, stderr, status = validate(directory)
    unless status.success? && stderr.empty? &&
           stdout.include?("Agent Skill repository structure and profile contracts are valid.")
      FAILURES << "#{label}: expected success; status=#{status.exitstatus.inspect}, " \
                  "stdout=#{stdout.inspect}, stderr=#{stderr.inspect}"
    end
  end
end

def expect_failure(label, diagnostic)
  materialize do |directory|
    yield directory
    run!("git", "add", "-A", chdir: directory)
    stdout, stderr, status = validate(directory)
    if status.success?
      FAILURES << "#{label}: expected validation failure; stdout=#{stdout.inspect}"
    elsif stderr != "#{diagnostic}\n"
      FAILURES << "#{label}: expected only #{diagnostic.inspect}; stderr=#{stderr.inspect}"
    end
  end
end

unless File.file?(CANONICAL_LICENSE_PATH) && !File.symlink?(CANONICAL_LICENSE_PATH) &&
       File.read(CANONICAL_LICENSE_PATH, encoding: "UTF-8") == EXPECTED_CANONICAL_LICENSE
  FAILURES << "canonical template license: expected the exact maintained MIT-0 text"
end

license_guidance = if File.file?(LICENSE_TEMPLATE_PATH) && !File.symlink?(LICENSE_TEMPLATE_PATH)
                     File.read(LICENSE_TEMPLATE_PATH, encoding: "UTF-8")
                   else
                     ""
                   end
[
  "keep LICENSE to use MIT-0 for the concrete skill",
  "replace LICENSE with another license appropriate for the concrete skill",
  "remove LICENSE.template"
].each do |required_text|
  unless license_guidance.include?(required_text)
    FAILURES << "license template guidance: missing #{required_text.inspect}"
  end
end

expect_success("completed instruction-only skill")

expect_success("concrete README is allowed") do |directory|
  File.write(File.join(directory, "README.md"), CONCRETE_README, encoding: "UTF-8")
end

expect_success("concrete skill may retain canonical MIT-0 license") do |directory|
  FileUtils.cp(CANONICAL_LICENSE_PATH, File.join(directory, "LICENSE"), preserve: true)
end

expect_failure(
  "license placeholder residue",
  "A concrete skill must replace or remove LICENSE.template."
) do |directory|
  File.write(
    File.join(directory, "LICENSE.template"),
    "Select a license appropriate for the concrete skill.\n",
    encoding: "UTF-8"
  )
end

expect_failure(
  "canonical README identity residue",
  "A concrete skill must replace or remove the canonical template README identity."
) do |directory|
  File.write(
    File.join(directory, "README.md"),
    CANONICAL_TEMPLATE_README,
    encoding: "UTF-8"
  )
end

unless FAILURES.empty?
  FAILURES.each { |failure| warn failure }
  exit 1
end

puts "Concrete skill completion hygiene tests passed."
