#!/usr/bin/env ruby
# frozen_string_literal: true

require "rbconfig"

DIRECT_VALIDATORS = %w[
  .github/scripts/validate-interface-routing-contract.rb
  .github/scripts/validate-decomposed-interface-contracts.rb
  .github/scripts/validate-selected-contract-scalar-placeholders.rb
  .github/scripts/validate-cli-structured-output-contract.rb
  .github/scripts/validate-cli-exit-code-contract.rb
  .github/scripts/validate-mcp-runtime-authority.rb
  .github/scripts/validate-interface-runtime-consistency.rb
  .github/scripts/validate-bundled-mcp-client-consistency.rb
  .github/scripts/validate-interface-summary-details.rb
].freeze

DEFAULT_RULE_VALIDATORS = %w[
  .github/scripts/validate-core-profile-contracts.rb
  .github/scripts/validate-extended-profile-contracts.rb
  .github/scripts/validate-concrete-profile-consistency.rb
  .github/scripts/validate-review-followup-contracts.rb
  .github/scripts/validate-late-review-contracts.rb
].freeze

rule_validators = ARGV.empty? ? DEFAULT_RULE_VALIDATORS : ARGV

(DIRECT_VALIDATORS + rule_validators).uniq.each do |validator|
  unless File.file?(validator)
    warn "Missing profile validator: #{validator}"
    exit 1
  end

  success = system({ "RUBYOPT" => nil }, RbConfig.ruby, validator)
  exit($?.exitstatus || 1) unless success
end

puts "All requested Agent Skill profile validators passed."
