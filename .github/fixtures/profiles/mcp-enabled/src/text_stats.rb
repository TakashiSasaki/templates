# frozen_string_literal: true

module TextStatsMcp
  VERSION = "1.0.0"
  PROTOCOL_VERSION = "2025-11-25"
  TOOL_NAME = "text_stats"

  module_function

  def analyze(text)
    {
      "bytes" => text.bytesize,
      "lines" => text.empty? ? 0 : text.lines.count,
      "words" => text.scan(/\S+/).length
    }
  end
end
