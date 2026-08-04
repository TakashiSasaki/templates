#!/usr/bin/env ruby
# frozen_string_literal: true

require "open3"
require "rbconfig"
require "tmpdir"

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

BASE_ENVIRONMENT = {
  "RUBYOPT" => nil,
  "GIT_DIR" => nil,
  "GIT_WORK_TREE" => nil,
  "GIT_INDEX_FILE" => nil
}.freeze

PROBE_ENVIRONMENT = BASE_ENVIRONMENT.merge("LC_ALL" => "C").freeze

def requested_validators
  specs = DIRECT_VALIDATORS.map { |validator| [validator, true] }
  specs.concat(
    if ARGV.empty?
      DEFAULT_RULE_VALIDATORS.map { |validator| [validator, true] }
    else
      ARGV.map { |validator| [validator, false] }
    end
  )
  specs
end

def run_validators(validator_specs, environment)
  seen_paths = {}
  validator_specs.each do |validator, bundled|
    path = bundled ? File.expand_path(validator, __dir__) : File.expand_path(validator)
    next if seen_paths[path]

    seen_paths[path] = true
    unless File.file?(path)
      warn "Missing profile validator: #{validator}"
      return 1
    end

    success = system(environment, RbConfig.ruby, path)
    return($?.exitstatus || 1) unless success
  end

  puts "All requested Agent Skill profile validators passed."
  0
end

def git_worktree_state
  output, status = Open3.capture2e(
    PROBE_ENVIRONMENT,
    "git",
    "rev-parse",
    "--is-inside-work-tree"
  )
  return [:present, output] if status.success? && output.strip == "true"
  return [:absent, output] if !status.success? && output.include?("not a git repository")

  [:error, output]
rescue Errno::ENOENT => e
  [:error, e.message]
end

validator_specs = requested_validators
state, diagnostic = git_worktree_state

case state
when :present
  exit run_validators(validator_specs, BASE_ENVIRONMENT)
when :absent
  Dir.mktmpdir("profile-contract-git-index") do |temporary|
    git_dir = File.join(temporary, "repository.git")
    init_output, init_status = Open3.capture2e(
      BASE_ENVIRONMENT,
      "git",
      "init",
      "--quiet",
      "--bare",
      git_dir
    )
    unless init_status.success?
      warn "Unable to create a temporary Git index for archive validation: #{init_output.strip}"
      exit 1
    end

    environment = BASE_ENVIRONMENT.merge(
      "GIT_DIR" => git_dir,
      "GIT_WORK_TREE" => Dir.pwd,
      "GIT_INDEX_FILE" => File.join(git_dir, "index")
    )
    index_output, index_status = Open3.capture2e(environment, "git", "read-tree", "--empty")
    unless index_status.success?
      warn "Unable to initialize a temporary Git index for archive validation: #{index_output.strip}"
      exit 1
    end

    exit run_validators(validator_specs, environment)
  end
else
  warn "Unable to determine whether the skill root has Git metadata: #{diagnostic.strip}"
  exit 1
end
