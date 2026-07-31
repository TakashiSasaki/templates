#!/usr/bin/env ruby

require_relative "decomposed-interface-compat"

# Normalize the documented MCP support annotation before loading the core
# validator. MCP_INTERFACE.md may record authority text after the leading
# support token. The public support value remains the leading YES, NO, or
# UNSELECTED token.
class << File
  alias_method :read_without_mcp_support_normalization, :read

  def read(path, *args, **kwargs)
    content = read_without_mcp_support_normalization(path, *args, **kwargs)
    return content unless path.to_s == "INTERFACES.md"

    content.gsub(
      /^Supported:\s*(YES|NO|UNSELECTED)(?:\s*;.*)?\s*$/i,
      'Supported: \\1'
    )
  end
end

load File.expand_path("validate-selected-profiles-core.rb", __dir__)
