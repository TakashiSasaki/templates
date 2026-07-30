#!/usr/bin/env ruby
# frozen_string_literal: true

require "rbconfig"

DIRECT_VALIDATOR = ".github/scripts/validate-decomposed-interface-contracts.rb"
DEFAULT_VALIDATORS = %w[
  .github/scripts/validate-selected-profiles.rb
  .github/scripts/validate-extended-profile-contracts.rb
  .github/scripts/validate-concrete-profile-consistency.rb
  .github/scripts/validate-review-followup-contracts.rb
  .github/scripts/validate-late-review-contracts.rb
].freeze

validators = [DIRECT_VALIDATOR] + (ARGV.empty? ? DEFAULT_VALIDATORS : ARGV)
shim = File.expand_path("decomposed-interface-compat.rb", __dir__)
rubyopt_parts = [ENV["RUBYOPT"], "-r#{shim}"].compact.reject(&:empty?)
environment = { "RUBYOPT" => rubyopt_parts.join(" ") }

validators.uniq.each do |validator|
  unless File.file?(validator)
    warn "Missing profile validator: #{validator}"
    exit 1
  end

  success = system(environment, RbConfig.ruby, validator)
  exit($?.exitstatus || 1) unless success
end

puts "All requested Agent Skill profile validators passed."
