#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "pathname"
require "set"

ROOT = Pathname.new(File.expand_path("../..", __dir__))
CLASSIFICATION = ROOT.join("docs/architecture/distribution-classification.json")
IGNORED_LOCAL_ENTRIES = Set.new(%w[.git .bundle .ruby-lsp .DS_Store]).freeze

failures = []

begin
  value = JSON.parse(CLASSIFICATION.read(encoding: "UTF-8"))
rescue StandardError => e
  warn "distribution classification could not be read: #{e.class}: #{e.message}"
  exit 1
end

unless value.is_a?(Hash)
  failures << "distribution classification must be a JSON object"
  value = {}
end

classification = value["topLevelClassification"]
expected_categories = %w[distribution maintainer split].to_set
unless classification.is_a?(Hash) && classification.keys.to_set == expected_categories
  failures << "topLevelClassification must contain exactly distribution, split, and maintainer"
  classification = {}
end

classified = []
classification.each do |category, entries|
  unless entries.is_a?(Array) && entries.all? { |entry| entry.is_a?(String) && !entry.empty? }
    failures << "#{category} entries must be non-empty strings"
    next
  end
  failures << "#{category} entries must be sorted" unless entries == entries.sort
  failures << "#{category} entries must be unique" unless entries.uniq == entries
  classified.concat(entries)
end

failures << "top-level entries may not be multiply classified" unless classified.uniq == classified
actual = ROOT.children.filter_map do |path|
  next if IGNORED_LOCAL_ENTRIES.include?(path.basename.to_s)

  path.basename.to_s
end.sort
failures << "top-level classification mismatch: expected #{actual.inspect}, got #{classified.sort.inspect}" unless actual == classified.sort
failures << "template must be the sole distribution top-level entry" unless classification["distribution"] == ["template"]
failures << "distribution manifest must remain maintainer-owned" unless classification.fetch("maintainer", []).include?("distribution-manifest.json")

failures << "schemaVersion must be integer 1" unless value["schemaVersion"] == 1
failures << "targetDistributionRoot must be template" unless value["targetDistributionRoot"] == "template"
failures << "directCopyDestination must be ." unless value["directCopyDestination"] == "."
failures << "contentTransformationAllowed must be false" unless value["contentTransformationAllowed"] == false

roots = value["targetSourceRoots"]
expected_roots = {
  "distribution" => "template",
  "maintainer" => ".",
  "publicationInterface" => "docs/publication-catalog.json"
}
failures << "targetSourceRoots mismatch" unless roots == expected_roots
expected_roots.each_value do |path_text|
  path = Pathname.new(path_text)
  failures << "unsafe target source root #{path_text.inspect}" if path.absolute? || path.each_filename.include?("..") || path.each_filename.any? { |part| part.downcase == ".git" }
end

profile_model = value["profileModel"]
expected_composable = %w[
  asset-driven
  browser-interface
  headless-service
  knowledge-augmented
  mcp-enabled
  packaged-cli
  script-assisted
]
unless profile_model.is_a?(Hash)
  failures << "profileModel must be an object"
else
  failures << "templateMarker must remain template-scaffold" unless profile_model["templateMarker"] == "template-scaffold"
  failures << "instruction-only must remain the sole exclusive profile" unless profile_model["exclusiveProfiles"] == ["instruction-only"]
  failures << "composable profiles changed" unless profile_model["composableProfiles"] == expected_composable
  failures << "composition rule must retain required-contract union" unless profile_model["compositionRule"] == "union-of-required-contracts"
end

rules = value["requiredSeparationRules"]
unless rules.is_a?(Array) && rules.length >= 6 && rules.all? { |rule| rule.is_a?(String) && !rule.empty? }
  failures << "requiredSeparationRules must contain at least six non-empty strings"
else
  combined = rules.join(" ").downcase
  %w[branch\ root concrete\ skill\ root escape\ template publication profile clean-room].each do |term|
    failures << "required separation rules omit #{term.tr('\\', ' ')}" unless combined.include?(term.tr("\\", " "))
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Skill source and distribution boundary tests passed."
