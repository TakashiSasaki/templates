#!/usr/bin/env ruby
# frozen_string_literal: true

# Source-maintainer parity shim. The downstream implementation remains canonical
# under template/.github/scripts; do not duplicate MCP extension logic here.

python = ENV.fetch("PYTHON", "python3")
validator = File.expand_path(
  "../../template/.github/scripts/validate_mcp_extensions.py",
  __dir__
)

exec(python, validator)
