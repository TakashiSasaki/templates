#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "pathname"

module PublicationCatalog
  class ValidationError < StandardError; end

  Document = Struct.new(:id, :source, :optional, :home, keyword_init: true)

  ROOT_KEYS = %w[documents schema_version].freeze
  DOCUMENT_KEYS = %w[home id optional source].freeze
  ID_PATTERN = /\A[a-z0-9]+(?:-[a-z0-9]+)*\z/

  module_function

  def validate(catalog_path, root: Dir.pwd)
    root_path = Pathname.new(root).expand_path
    raise ValidationError, "Repository root does not exist: #{root_path}" unless root_path.directory?

    catalog = read_catalog(Pathname.new(catalog_path))
    validate_exact_keys(catalog, ROOT_KEYS, "publication catalog")

    unless catalog["schema_version"].is_a?(Integer) && catalog["schema_version"] == 1
      raise ValidationError, "publication catalog schema_version must be 1 and use an integer JSON value"
    end

    raw_documents = catalog["documents"]
    unless raw_documents.is_a?(Array) && !raw_documents.empty?
      raise ValidationError, "publication catalog documents must be a non-empty array"
    end

    documents = raw_documents.each_with_index.map do |raw_document, index|
      parse_document(raw_document, index, root_path)
    end

    duplicate_id = duplicate_value(documents.map(&:id))
    raise ValidationError, "Duplicate publication document id: #{duplicate_id}" if duplicate_id

    duplicate_source = duplicate_value(documents.map(&:source))
    if duplicate_source
      raise ValidationError, "Duplicate publication document source: #{duplicate_source}"
    end

    home_documents = documents.select(&:home)
    unless home_documents.length == 1
      raise ValidationError, "publication catalog must select exactly one home document"
    end
    if home_documents.first.optional
      raise ValidationError, "publication catalog home document must not be optional"
    end

    documents
  end

  def read_catalog(path)
    if path.symlink?
      raise ValidationError, "Publication catalog must not be a symlink: #{path}"
    end

    content = path.binread.force_encoding(Encoding::UTF_8)
    unless content.valid_encoding?
      raise ValidationError, "Invalid publication catalog JSON #{path}: content is not valid UTF-8"
    end

    JSON.parse(content)
  rescue Errno::ENOENT
    raise ValidationError, "Publication catalog does not exist: #{path}"
  rescue Errno::EACCES => e
    raise ValidationError, "Unable to read publication catalog #{path}: #{e.message}"
  rescue JSON::ParserError => e
    raise ValidationError, "Invalid publication catalog JSON #{path}: #{e.message}"
  end

  def parse_document(raw_document, index, root_path)
    field = "documents[#{index}]"
    unless raw_document.is_a?(Hash)
      raise ValidationError, "#{field} must be an object"
    end

    validate_exact_keys(raw_document, DOCUMENT_KEYS, field)

    id = raw_document["id"]
    unless id.is_a?(String) && ID_PATTERN.match?(id)
      raise ValidationError, "#{field}.id must use lowercase kebab-case"
    end

    source = validate_source(raw_document["source"], "#{field}.source")
    optional = raw_document["optional"]
    home = raw_document["home"]
    unless optional == true || optional == false
      raise ValidationError, "#{field}.optional must be boolean"
    end
    unless home == true || home == false
      raise ValidationError, "#{field}.home must be boolean"
    end

    validate_source_file(root_path, source, field)
    Document.new(id: id, source: source, optional: optional, home: home)
  end

  def validate_exact_keys(value, expected, field)
    unless value.is_a?(Hash)
      raise ValidationError, "#{field} must be an object"
    end

    actual = value.keys.sort
    return if actual == expected.sort

    missing = expected - value.keys
    unknown = value.keys - expected
    details = []
    details << "missing: #{missing.sort.join(', ')}" unless missing.empty?
    details << "unsupported: #{unknown.sort.join(', ')}" unless unknown.empty?
    raise ValidationError, "#{field} fields are invalid (#{details.join('; ')})"
  end

  def validate_source(value, field)
    unless value.is_a?(String) && !value.empty?
      raise ValidationError, "#{field} must be a non-empty string"
    end

    parts = value.split("/", -1)
    unsafe = value.start_with?("/") || value.include?("\\") || value.include?("\0") ||
             parts.any? { |part| part.empty? || part == "." || part == ".." }
    raise ValidationError, "#{field} must be a safe relative POSIX path: #{value.inspect}" if unsafe

    unless value.downcase.end_with?(".md")
      raise ValidationError, "#{field} must identify a Markdown file"
    end

    value
  end

  def validate_source_file(root_path, source, field)
    candidate = root_path
    source.split("/").each do |part|
      candidate = candidate.join(part)
      if candidate.symlink?
        raise ValidationError, "#{field} traverses a symlink: #{source}"
      end
    end

    unless candidate.file?
      raise ValidationError, "#{field} does not identify an existing regular file: #{source}"
    end
  end

  def duplicate_value(values)
    seen = {}
    values.each do |value|
      return value if seen[value]

      seen[value] = true
    end
    nil
  end
end

if $PROGRAM_NAME == __FILE__
  root = Pathname.new(ARGV[1] || Dir.pwd).expand_path
  catalog_path = ARGV[0] ? Pathname.new(ARGV[0]) : root.join("docs/publication-catalog.json")

  begin
    documents = PublicationCatalog.validate(catalog_path, root: root)
  rescue PublicationCatalog::ValidationError => e
    warn "validate-publication-catalog.rb: #{e.message}"
    exit 1
  end

  puts "Publication catalog valid: #{documents.length} document(s)."
end
