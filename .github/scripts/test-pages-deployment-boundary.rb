#!/usr/bin/env ruby
# frozen_string_literal: true

require "pathname"

ROOT = Pathname.new(__dir__).join("../..").expand_path
WORKFLOWS = ROOT.join(".github/workflows")
COMPATIBILITY = WORKFLOWS.join("check-site-compatibility.yml")
REMOVED_DISPATCHER = WORKFLOWS.join("pages.yml")

abort "main Pages dispatcher still exists" if REMOVED_DISPATCHER.exist?
abort "compatibility workflow is missing" unless COMPATIBILITY.file?

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
  "contents: read"
]
required.each do |token|
  abort "compatibility workflow is missing #{token.inspect}" unless compatibility.include?(token)
end

abort "compatibility workflow still passes a deploy input" if compatibility.match?(/^\s+deploy:/)
abort "compatibility workflow retains OIDC write permission" if compatibility.include?("id-token: write")

puts "main workflows contain no GitHub Pages deployment route"
