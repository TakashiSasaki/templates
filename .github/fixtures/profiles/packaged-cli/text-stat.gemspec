# frozen_string_literal: true

require_relative "src/text_stat"

Gem::Specification.new do |spec|
  spec.name = "text-stat"
  spec.version = TextStat::VERSION
  spec.summary = "Deterministic text statistics CLI fixture"
  spec.description = "Computes byte, line, and word counts with human and JSON output."
  spec.authors = ["TakashiSasaki/templates maintainers"]
  spec.license = "MIT"
  spec.homepage = "https://github.com/TakashiSasaki/templates"
  spec.files = Dir["bin/*", "src/**/*.rb"]
  spec.bindir = "bin"
  spec.executables = ["text-stat"]
  spec.require_paths = ["src"]
  spec.required_ruby_version = ">= 3.1"
end
