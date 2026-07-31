#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "pathname"
require "tmpdir"
require_relative "validate-publication-catalog"

failures = []

[1.0, JSON.parse("1e0")].each do |schema_version|
  Dir.mktmpdir("publication-schema-version-test") do |directory|
    root = Pathname.new(directory)
    root.join("docs").mkpath
    root.join("README.md").write("# Overview\n", encoding: "UTF-8")
    catalog_path = root.join("docs/publication-catalog.json")
    catalog_path.write(
      JSON.generate(
        "schema_version" => schema_version,
        "documents" => [
          {
            "id" => "overview",
            "source" => "README.md",
            "optional" => false,
            "home" => true
          }
        ]
      ),
      encoding: "UTF-8"
    )

    begin
      PublicationCatalog.validate(catalog_path, root: root)
      failures << "schema_version #{schema_version.inspect}: validation unexpectedly succeeded"
    rescue PublicationCatalog::ValidationError => e
      unless /schema_version must be 1 and use an integer JSON value/.match?(e.message)
        failures << "schema_version #{schema_version.inspect}: unexpected diagnostic #{e.message.inspect}"
      end
    rescue StandardError => e
      failures << "schema_version #{schema_version.inspect}: unexpected #{e.class}: #{e.message}"
    end
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Publication schema-version type tests passed."
