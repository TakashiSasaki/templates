#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "json"
require "pathname"
require "tmpdir"
require_relative "validate-publication-catalog"

BASE_DOCUMENTS = [
  {
    "id" => "overview",
    "source" => "README.md",
    "optional" => false,
    "home" => true
  },
  {
    "id" => "guide",
    "source" => "docs/guide.md",
    "optional" => true,
    "home" => false
  }
].freeze


def deep_copy(value)
  Marshal.load(Marshal.dump(value))
end


def prepare_repository
  Dir.mktmpdir("publication-catalog-test") do |directory|
    root = Pathname.new(directory)
    root.join("docs").mkpath
    root.join("README.md").write("# Overview\n", encoding: "UTF-8")
    root.join("docs/guide.md").write("# Guide\n", encoding: "UTF-8")
    yield root
  end
end


def write_catalog(root, documents: deep_copy(BASE_DOCUMENTS), schema_version: 1, extra: {})
  catalog = {
    "schema_version" => schema_version,
    "documents" => documents
  }.merge(extra)
  path = root.join("docs/publication-catalog.json")
  path.write(JSON.pretty_generate(catalog) + "\n", encoding: "UTF-8")
  path
end

failures = []

prepare_repository do |root|
  begin
    documents = PublicationCatalog.validate(write_catalog(root), root: root)
    expected = %w[overview guide]
    actual = documents.map(&:id)
    failures << "valid catalog: expected #{expected.inspect}, got #{actual.inspect}" unless actual == expected
  rescue StandardError => e
    failures << "valid catalog: unexpected #{e.class}: #{e.message}"
  end
end

invalid_cases = [
  {
    name: "rejects unsupported schema versions",
    pattern: /schema_version must be 1/,
    mutate: lambda do |root|
      write_catalog(root, schema_version: 2)
    end
  },
  {
    name: "rejects unsupported root fields",
    pattern: /unsupported: navigation/,
    mutate: lambda do |root|
      write_catalog(root, extra: { "navigation" => [] })
    end
  },
  {
    name: "rejects duplicate document ids",
    pattern: /Duplicate publication document id: overview/,
    mutate: lambda do |root|
      documents = deep_copy(BASE_DOCUMENTS)
      documents[1]["id"] = "overview"
      write_catalog(root, documents: documents)
    end
  },
  {
    name: "rejects duplicate source paths",
    pattern: /Duplicate publication document source: README\.md/,
    mutate: lambda do |root|
      documents = deep_copy(BASE_DOCUMENTS)
      documents[1]["source"] = "README.md"
      write_catalog(root, documents: documents)
    end
  },
  {
    name: "rejects invalid document ids",
    pattern: /lowercase kebab-case/,
    mutate: lambda do |root|
      documents = deep_copy(BASE_DOCUMENTS)
      documents[1]["id"] = "Guide_Page"
      write_catalog(root, documents: documents)
    end
  },
  {
    name: "rejects unsafe parent traversal",
    pattern: /safe relative POSIX path/,
    mutate: lambda do |root|
      documents = deep_copy(BASE_DOCUMENTS)
      documents[1]["source"] = "../guide.md"
      write_catalog(root, documents: documents)
    end
  },
  {
    name: "rejects backslash paths",
    pattern: /safe relative POSIX path/,
    mutate: lambda do |root|
      documents = deep_copy(BASE_DOCUMENTS)
      documents[1]["source"] = "docs\\guide.md"
      write_catalog(root, documents: documents)
    end
  },
  {
    name: "rejects non-Markdown sources",
    pattern: /must identify a Markdown file/,
    mutate: lambda do |root|
      root.join("docs/guide.txt").write("guide\n", encoding: "UTF-8")
      documents = deep_copy(BASE_DOCUMENTS)
      documents[1]["source"] = "docs/guide.txt"
      write_catalog(root, documents: documents)
    end
  },
  {
    name: "rejects missing source files",
    pattern: /existing regular file/,
    mutate: lambda do |root|
      documents = deep_copy(BASE_DOCUMENTS)
      documents[1]["source"] = "docs/missing.md"
      write_catalog(root, documents: documents)
    end
  },
  {
    name: "rejects symlinked source files",
    pattern: /traverses a symlink/,
    mutate: lambda do |root|
      root.join("docs/guide.md").delete
      File.symlink(root.join("README.md"), root.join("docs/guide.md"))
      write_catalog(root)
    end
  },
  {
    name: "rejects catalogs without a home document",
    pattern: /exactly one home document/,
    mutate: lambda do |root|
      documents = deep_copy(BASE_DOCUMENTS)
      documents.each { |document| document["home"] = false }
      write_catalog(root, documents: documents)
    end
  },
  {
    name: "rejects multiple home documents",
    pattern: /exactly one home document/,
    mutate: lambda do |root|
      documents = deep_copy(BASE_DOCUMENTS)
      documents.each { |document| document["home"] = true }
      write_catalog(root, documents: documents)
    end
  },
  {
    name: "rejects an optional home document",
    pattern: /home document must not be optional/,
    mutate: lambda do |root|
      documents = deep_copy(BASE_DOCUMENTS)
      documents[0]["optional"] = true
      write_catalog(root, documents: documents)
    end
  },
  {
    name: "rejects non-boolean optional values",
    pattern: /optional must be boolean/,
    mutate: lambda do |root|
      documents = deep_copy(BASE_DOCUMENTS)
      documents[1]["optional"] = "yes"
      write_catalog(root, documents: documents)
    end
  },
  {
    name: "rejects missing document fields",
    pattern: /missing: home/,
    mutate: lambda do |root|
      documents = deep_copy(BASE_DOCUMENTS)
      documents[1].delete("home")
      write_catalog(root, documents: documents)
    end
  }
]

invalid_cases.each do |test_case|
  prepare_repository do |root|
    catalog_path = test_case.fetch(:mutate).call(root)
    begin
      PublicationCatalog.validate(catalog_path, root: root)
      failures << "#{test_case.fetch(:name)}: validation unexpectedly succeeded"
    rescue PublicationCatalog::ValidationError => e
      unless test_case.fetch(:pattern).match?(e.message)
        failures << "#{test_case.fetch(:name)}: unexpected diagnostic #{e.message.inspect}"
      end
    rescue StandardError => e
      failures << "#{test_case.fetch(:name)}: unexpected #{e.class}: #{e.message}"
    end
  end
end

unless failures.empty?
  failures.each { |failure| warn failure }
  exit 1
end

puts "Publication catalog tests passed (#{invalid_cases.length + 1} cases)."
