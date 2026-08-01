# frozen_string_literal: true

require "json"
require "optparse"

module TextStat
  VERSION = "1.0.0"
  CONTRACT_VERSION = "1"

  module_function

  def analyze(text)
    {
      "bytes" => text.bytesize,
      "lines" => text.empty? ? 0 : text.lines.count,
      "words" => text.scan(/\S+/).length
    }
  end

  class CLI
    def self.run(argv, stdin: $stdin, stdout: $stdout, stderr: $stderr)
      output = "human"
      parser = OptionParser.new do |options|
        options.banner = "Usage: text-stat [--output human|json] INPUT"
        options.on("--output FORMAT", %w[human json], "Select human or JSON output") do |format|
          output = format
        end
        options.on("--version", "Print the package version") do
          stdout.puts(VERSION)
          return 0
        end
        options.on("-h", "--help", "Show this help") do
          stdout.puts(options)
          return 0
        end
      end

      begin
        parser.parse!(argv)
      rescue OptionParser::ParseError => error
        stderr.puts(error.message)
        return 2
      end

      unless argv.length == 1
        stderr.puts("exactly one INPUT path or - is required")
        return 2
      end

      begin
        text = argv.first == "-" ? stdin.read : File.binread(argv.first)
      rescue SystemCallError, IOError => error
        stderr.puts("unable to read input: #{error.message}")
        return 3
      end

      text = text.force_encoding(Encoding::UTF_8)
      unless text.valid_encoding?
        stderr.puts("input is not valid UTF-8")
        return 2
      end

      result = TextStat.analyze(text)
      if output == "json"
        stdout.puts(JSON.generate(
          "contractVersion" => CONTRACT_VERSION,
          "ok" => true,
          "result" => result
        ))
      else
        stdout.puts("bytes: #{result.fetch("bytes")}")
        stdout.puts("lines: #{result.fetch("lines")}")
        stdout.puts("words: #{result.fetch("words")}")
      end
      0
    end
  end
end
