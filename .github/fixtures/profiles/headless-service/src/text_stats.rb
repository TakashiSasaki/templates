# frozen_string_literal: true

require "fileutils"
require "json"
require "socket"

module TextStatsService
  VERSION = "1.0.0"
  CONTRACT_VERSION = 1

  module_function

  def analyze(text)
    {
      "bytes" => text.bytesize,
      "lines" => text.empty? ? 0 : text.lines.count,
      "words" => text.scan(/\S+/).length
    }
  end

  # The health client is prepended before service/server.rb reopens ServerCommand,
  # so this bounded implementation remains authoritative for lifecycle probes.
  module BoundedHealthClient
    def read_bounded_health_response(bind, port, path)
      socket = TCPSocket.new(bind, port)
      socket.write(
        "GET #{path} HTTP/1.1\r\n" \
        "Host: #{bind}:#{port}\r\n" \
        "Accept: application/json\r\n" \
        "Connection: close\r\n\r\n"
      )

      buffered = +"".b
      header_end = nil
      until header_end
        buffered << socket.readpartial(512)
        header_end = buffered.index("\r\n\r\n")
        if header_end
          if header_end + 4 > self::HEALTH_HEADER_MAX_BYTES
            raise ConfigurationError,
                  "health response headers exceed #{self::HEALTH_HEADER_MAX_BYTES} bytes"
          end
        elsif buffered.bytesize > self::HEALTH_HEADER_MAX_BYTES
          raise ConfigurationError,
                "health response headers exceed #{self::HEALTH_HEADER_MAX_BYTES} bytes"
        end
      end

      serialized_headers = buffered.byteslice(0, header_end + 4)
      response_body = buffered.byteslice(header_end + 4..).to_s.b
      status_line, *header_lines = serialized_headers.split("\r\n")
      status_match = /\AHTTP\/1\.[01] (\d{3})(?: .*)?\z/.match(status_line.to_s)
      raise ConfigurationError, "invalid health response status line" unless status_match

      headers = {}
      header_lines.each do |line|
        next if line.empty?

        name, value = line.split(":", 2)
        unless name && value && /\A[!#$%&'*+.^_`|~0-9A-Za-z-]+\z/.match?(name)
          raise ConfigurationError, "invalid health response header"
        end
        headers[name.downcase] = value.strip
      end

      expected_body_bytes = nil
      if headers.key?("content-length")
        raw_length = headers.fetch("content-length")
        unless /\A\d+\z/.match?(raw_length)
          raise ConfigurationError, "invalid health response Content-Length"
        end
        expected_body_bytes = Integer(raw_length, 10)
        if expected_body_bytes > self::HEALTH_RESPONSE_MAX_BYTES
          raise ConfigurationError,
                "health response exceeds #{self::HEALTH_RESPONSE_MAX_BYTES} bytes"
        end
        while response_body.bytesize < expected_body_bytes
          response_body << socket.readpartial([512, expected_body_bytes - response_body.bytesize].min)
        end
        response_body = response_body.byteslice(0, expected_body_bytes)
        return [status_match[1], response_body]
      end

      loop do
        if response_body.bytesize > self::HEALTH_RESPONSE_MAX_BYTES
          raise ConfigurationError,
                "health response exceeds #{self::HEALTH_RESPONSE_MAX_BYTES} bytes"
        end
        response_body << socket.readpartial(512)
      end
    rescue EOFError
      complete_declared_body = expected_body_bytes.nil? || response_body&.bytesize == expected_body_bytes
      if complete_declared_body && response_body &&
         response_body.bytesize <= self::HEALTH_RESPONSE_MAX_BYTES && status_match
        return [status_match[1], response_body]
      end
      raise ConfigurationError, "incomplete health response"
    ensure
      socket&.close
    end
  end

  # Creation permissions are constrained by the process umask. Re-apply and
  # verify the lifecycle-record mode through the already-open descriptor so a
  # restrictive umask cannot publish a record that --stop and cleanup reject.
  module SecurePidRecordWriter
    def write_pid_record(path, record)
      FileUtils.mkdir_p(File.dirname(path))
      if File.exist?(path) || File.symlink?(path)
        raise ConfigurationError, "Headless service PID file already exists: #{path}"
      end

      File.open(path, File::WRONLY | File::CREAT | File::EXCL, 0o600) do |file|
        file.chmod(0o600)
        unless (file.stat.mode & 0o777) == 0o600
          raise ConfigurationError, "Headless service PID file must have mode 0600: #{path}"
        end
        file.write(JSON.generate(record))
        file.write("\n")
      end
    rescue Errno::EEXIST
      raise ConfigurationError, "Headless service PID file already exists: #{path}"
    rescue SystemCallError => error
      raise ConfigurationError, "unable to create headless service PID file #{path}: #{error.message}"
    end
  end

  class ServerCommand; end
  ServerCommand.singleton_class.prepend(BoundedHealthClient)
  ServerCommand.singleton_class.prepend(SecurePidRecordWriter)
end
