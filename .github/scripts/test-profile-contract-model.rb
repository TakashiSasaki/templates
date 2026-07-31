#!/usr/bin/env ruby
# frozen_string_literal: true

require "tmpdir"
require_relative "lib/profile_contracts"

failures = []

check = lambda do |name, &block|
  block.call
rescue StandardError => error
  failures << "#{name}: #{error.class}: #{error.message}"
end

assert = lambda do |condition, message|
  raise message unless condition
end

check.call("parses one normalized profile declaration") do
  Dir.mktmpdir("profile-contract-model-test") do |directory|
    path = File.join(directory, "SKILL.md")
    File.write(path, "- Selected profiles: `packaged-cli, mcp-enabled`\n")
    selection = ProfileContracts::ProfileSelection.load(path)
    assert.call(selection.profiles == %w[packaged-cli mcp-enabled], selection.profiles.inspect)
    assert.call(selection.selected?("packaged-cli"), "packaged-cli was not selected")
    assert.call(!selection.template_scaffold?, "concrete selection reported as scaffold")
  end
end

check.call("rejects duplicate profile declarations") do
  Dir.mktmpdir("profile-contract-model-test") do |directory|
    path = File.join(directory, "SKILL.md")
    File.write(path, "Selected profiles: packaged-cli\nSelected profiles: mcp-enabled\n")
    begin
      ProfileContracts::ProfileSelection.load(path)
    rescue ProfileContracts::ParseError => error
      assert.call(error.message.include?("exactly one"), error.message)
      next
    end
    raise "duplicate declarations were accepted"
  end
end

check.call("rejects an empty profile declaration") do
  Dir.mktmpdir("profile-contract-model-test") do |directory|
    path = File.join(directory, "SKILL.md")
    File.write(path, "Selected profiles:\n")
    begin
      ProfileContracts::ProfileSelection.load(path)
    rescue ProfileContracts::ParseError => error
      assert.call(error.message.include?("at least one"), error.message)
      next
    end
    raise "empty profile declaration was accepted"
  end
end

check.call("extracts nested and peer Markdown sections") do
  document = ProfileContracts::MarkdownDocument.new(<<~MARKDOWN)
    ## Parent

    Parent value: retained

    ### Child

    Child value: retained

    ## Peer

    Peer value: excluded
  MARKDOWN
  parent = document.section("## Parent")
  child = document.section("### Child")
  assert.call(parent.include?("Child value: retained"), parent.inspect)
  assert.call(!parent.include?("Peer value: excluded"), parent.inspect)
  assert.call(child.include?("Child value: retained"), child.inspect)
end

check.call("normalizes scalar fields and table cells") do
  document = ProfileContracts::MarkdownDocument.new(<<~MARKDOWN)
    Mode selector: `--json`

    | Item | Value |
    |---|---|
    | TBD | `JSON` |
    | Failure | Validation \\| runtime failure |
  MARKDOWN
  assert.call(document.field("Mode selector") == "--json", document.field("Mode selector").inspect)
  assert.call(document.table_rows[1] == ["TBD", "JSON"], document.table_rows.inspect)
  assert.call(
    document.table_rows.last == ["Failure", "Validation \\| runtime failure"],
    document.table_rows.inspect
  )
  table_values = document.each_scalar.select { |entry| entry.kind == :table }.map(&:value)
  assert.call(table_values.include?("TBD"), table_values.inspect)
  assert.call(table_values.include?("Validation \\| runtime failure"), table_values.inspect)
end

check.call("applies shared unresolved and concrete value policy") do
  policy = ProfileContracts::ValuePolicy
  assert.call(policy.unresolved_scalar?("`TBD`"), "TBD was not unresolved")
  assert.call(policy.unresolved_scalar?("details forthcoming"), "forthcoming phrase was not unresolved")
  assert.call(!policy.unresolved_scalar?("documented behavior"), "concrete prose was unresolved")
  assert.call(policy.resolved?("NONE"), "NONE should be resolved")
  assert.call(!policy.concrete?("NONE"), "NONE should not be concrete")
  assert.call(policy.concrete?("successful completion"), "concrete value was rejected")
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Shared profile contract model tests passed."
