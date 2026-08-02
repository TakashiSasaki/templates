# frozen_string_literal: true

require_relative "text_stat"

module TextStatsMcp
  VERSION = TextStat::VERSION
  PROTOCOL_VERSION = "2025-11-25"
  TOOL_NAME = "text_stats"

  module_function

  def analyze(text)
    TextStat.analyze(text)
  end
end
