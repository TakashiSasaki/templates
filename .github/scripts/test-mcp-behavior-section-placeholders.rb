#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "open3"
require "rbconfig"
require "tmpdir"

validator = File.expand_path("validate-decomposed-interface-contracts.rb", __dir__)
fixture_source = File.read(File.expand_path("test-decomposed-interface-contracts.rb", __dir__))

extract_heredoc = lambda do |name|
  match = fixture_source.match(/^#{Regexp.escape(name)} = <<~MARKDOWN\n(.*?)^MARKDOWN\n/m)
  unless match
    warn "Could not extract #{name} fixture."
    exit 1
  end

  lines = match[1].lines
  indentation = lines.reject { |line| line.strip.empty? }.map { |line| line[/\A */].length }.min || 0
  lines.map { |line| line.sub(/\A {0,#{indentation}}/, "") }.join
end

valid_mcp = extract_heredoc.call("valid_mcp")

replace_section = lambda do |document, heading, replacement|
  level = heading[/\A#+/].length
  boundary = level == 2 ? "^##\\s|\\z" : "^(?:##|###)\\s|\\z"
  document.sub(
    Regexp.new("^#{Regexp.escape(heading)}\\s*$\\n.*?(?=#{boundary})", Regexp::MULTILINE),
    "#{heading}\n\n#{replacement}\n\n"
  )
end

headings = [
  "### Tool inventory, schemas, and caching",
  "### Lossless paginated tool-list output",
  "### Tool-call results and errors",
  "### Multiple calls and application state",
  "### Selected modern multi-round-trip requests",
  "### Selected initialization-era server-to-client requests",
  "### Cancellation, tasks, and extensions",
  "### Ownership and workspace policy"
]

cases = [
  ["accepts concrete caller-visible behavior sections", valid_mcp, true]
]

placeholders = [
  "TBD",
  "Details forthcoming.",
  "Describe the selected behavior here."
]

headings.each do |heading|
  placeholders.each do |placeholder|
    cases << [
      "rejects #{placeholder.inspect} under #{heading}",
      replace_section.call(valid_mcp, heading, placeholder),
      false
    ]
  end
end

failures = []

cases.each do |name, mcp_document, expected_success|
  Dir.mktmpdir("mcp-behavior-placeholder-test") do |directory|
    File.write(File.join(directory, "SKILL.md"), "Selected profiles: mcp-enabled\n")
    File.write(File.join(directory, "MCP_INTERFACE.md"), mcp_document)

    _stdout, stderr, status = Open3.capture3(
      { "RUBYOPT" => nil },
      RbConfig.ruby,
      validator,
      chdir: directory
    )

    next if status.success? == expected_success

    failures << "#{name}: expected success=#{expected_success}, got success=#{status.success?}; " \
                "diagnostics=#{stderr.strip.inspect}"
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "MCP caller-behavior placeholder rejection tests passed."
