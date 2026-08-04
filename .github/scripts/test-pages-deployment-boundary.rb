#!/usr/bin/env ruby
# frozen_string_literal: true

require "pathname"

ROOT = Pathname.new(__dir__).join("../..").expand_path
WORKFLOWS = ROOT.join(".github/workflows")
COMPATIBILITY = WORKFLOWS.join("pages.yml")
CONTRIBUTING = ROOT.join("CONTRIBUTING.md")

abort "build-only documentation compatibility workflow is missing" unless COMPATIBILITY.file?
abort "contributor guidance is missing" unless CONTRIBUTING.file?

workflow_files = WORKFLOWS.children.select { |path| path.file? && path.extname.match?(/\A\.ya?ml\z/) }
forbidden = {
  "Pages deployment action" => "actions/deploy-pages@",
  "Pages configuration action" => "actions/configure-pages@",
  "Pages artifact action" => "actions/upload-pages-artifact@",
  "Pages write permission" => "pages: write",
  "Pages environment" => "name: github-pages",
  "deployment-enabling input" => "deploy: true"
}

workflow_files.each do |path|
  text = path.read(encoding: "UTF-8")
  forbidden.each do |description, token|
    abort "#{description} remains in #{path.relative_path_from(ROOT)}" if text.include?(token)
  end
end

compatibility = COMPATIBILITY.read(encoding: "UTF-8")
required = [
  "uses: TakashiSasaki/templates/.github/workflows/build-pages.yml@site",
  "site_ref: site",
  "source_ref: ${{ github.event_name == 'pull_request' && github.sha || 'skill' }}",
  "contents: read",
  "CLI_INTERFACE.md",
  "MCP_INTERFACE.md"
]
required.each do |token|
  abort "compatibility workflow is missing #{token.inspect}" unless compatibility.include?(token)
end

trigger_block = compatibility.split("\npermissions:\n", 2).first
abort "skill push still triggers documentation workflow" if trigger_block.include?("\n  push:\n")
abort "compatibility workflow does not target skill pull requests" unless trigger_block.include?("\n      - skill\n")
abort "compatibility workflow still targets the removed main branch" if trigger_block.include?("\n      - main\n")
abort "skill workflow incorrectly claims a scheduled run" if trigger_block.include?("\n  schedule:\n")
abort "skill workflow lacks manual drift-check dispatch" unless trigger_block.include?("\n  workflow_dispatch:\n")
abort "compatibility workflow still passes a deploy input" if compatibility.match?(/^\s+deploy:/)
abort "compatibility workflow retains OIDC write permission" if compatibility.include?("id-token: write")

contributing = CONTRIBUTING.read(encoding: "UTF-8")
if contributing.include?("Publish template documentation")
  abort "contributor guidance still names the removed skill publication workflow"
end
unless contributing.include?("No workflow on `skill` deploys GitHub Pages")
  abort "contributor guidance does not state the skill deployment boundary"
end
unless contributing.include?("this `skill`-branch workflow does not claim a weekly scheduled run")
  abort "contributor guidance incorrectly claims a weekly skill schedule"
end

puts "skill workflows and contributor guidance contain no GitHub Pages deployment route"
