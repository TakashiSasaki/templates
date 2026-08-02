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
          return write_output(stdout, stderr) { stdout.puts(VERSION) }
        end
        options.on("-h", "--help", "Show this help") do
          return write_output(stdout, stderr) { stdout.puts(options) }
        end
      end

      begin
        parser.parse!(argv)
      rescue OptionParser::ParseError => error
        return write_diagnostic(stderr, error.message, 2)
      end

      unless argv.length == 1
        return write_diagnostic(stderr, "exactly one INPUT path or - is required", 2)
      end

      begin
        if argv.first == "-"
          stdin.binmode if stdin.respond_to?(:binmode)
          text = stdin.read
        else
          text = File.binread(argv.first)
        end
      rescue SystemCallError, IOError => error
        return write_diagnostic(stderr, "unable to read input: #{error.message}", 3)
      end

      text = text.force_encoding(Encoding::UTF_8)
      unless text.valid_encoding?
        return write_diagnostic(stderr, "input is not valid UTF-8", 2)
      end

      result = TextStat.analyze(text)
      write_output(stdout, stderr) do
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
      end
    end

    def self.write_diagnostic(stderr, message, status)
      stderr.puts(message)
      stderr.flush
      status
    rescue SystemCallError, IOError
      5
    end

    def self.write_output(stdout, stderr)
      yield
      stdout.flush
      0
    rescue SystemCallError, IOError => error
      write_diagnostic(stderr, "unable to write output: #{error.message}", 5)
    end
    private_class_method :write_diagnostic, :write_output
  end
end
