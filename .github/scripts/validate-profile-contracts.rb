#!/usr/bin/env ruby
# frozen_string_literal: true

require "rbconfig"

DIRECT_VALIDATORS = %w[
  validate-interface-routing-contract.rb
  validate-decomposed-interface-contracts.rb
  validate-selected-contract-scalar-placeholders.rb
  validate-cli-structured-output-contract.rb
  validate-cli-exit-code-contract.rb
  validate-mcp-runtime-authority.rb
  validate-interface-runtime-consistency.rb
  validate-bundled-mcp-client-consistency.rb
  validate-interface-summary-details.rb
].freeze

DEFAULT_RULE_VALIDATORS = %w[
  validate-core-profile-contracts.rb
  validate-extended-profile-contracts.rb
  validate-concrete-profile-consistency.rb
  validate-review-followup-contracts.rb
  validate-late-review-contracts.rb
].freeze

validator_specs = DIRECT_VALIDATORS.map { |validator| [validator, true] }
validator_specs.concat(
  if ARGV.empty?
    DEFAULT_RULE_VALIDATORS.map { |validator| [validator, true] }
  else
    ARGV.map { |validator| [validator, false] }
  end
)

seen_paths = {}
validator_specs.each do |validator, bundled|
  path = bundled ? File.expand_path(validator, __dir__) : File.expand_path(validator)
  next if seen_paths[path]

  seen_paths[path] = true
  unless File.file?(path)
    warn "Missing profile validator: #{validator}"
    exit 1
  end

  success = system({ "RUBYOPT" => nil }, RbConfig.ruby, path)
  exit($?.exitstatus || 1) unless success
end

puts "All requested Agent Skill profile validators passed."
