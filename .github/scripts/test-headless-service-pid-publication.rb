#!/usr/bin/env ruby
# frozen_string_literal: true

require "delegate"
require "fileutils"
require "json"
require "minitest/mock"
require "tmpdir"
require "timeout"
require_relative "../fixtures/profiles/headless-service/service/server"

class PartialWriteFile < SimpleDelegator
  def write(bytes)
    __getobj__.write(bytes.byteslice(0, 1))
    raise Errno::ENOSPC, "injected partial PID-record write"
  end
end

assert = lambda do |condition, message|
  raise message unless condition
end

writer = TextStatsService::ServerCommand
record = writer.current_pid_record
serialized = "#{JSON.generate(record)}\n"

Dir.mktmpdir("headless-service-pid-publication") do |directory|
  pid_file = File.join(directory, "service.pid")
  original_link = File.method(:link)
  link_entered = Queue.new
  release_link = Queue.new
  writer_error = nil
  writer_thread = nil

  blocking_link = lambda do |source, destination|
    link_entered << [source, destination]
    Timeout.timeout(5) { release_link.pop }
    original_link.call(source, destination)
  end

  begin
    File.stub(:link, blocking_link) do
      writer_thread = Thread.new do
        writer.write_pid_record(pid_file, record)
      rescue StandardError => error
        writer_error = error
      end

      staging_file, destination = Timeout.timeout(5) { link_entered.pop }
      assert.call(destination == pid_file, "PID record was published to an unexpected path")
      assert.call(
        !File.exist?(pid_file) && !File.symlink?(pid_file),
        "final PID pathname became visible before publication"
      )
      assert.call(File.binread(staging_file) == serialized, "staging PID record was incomplete")
      assert.call(
        (File.stat(staging_file).mode & 0o777) == 0o600,
        "staging PID record did not have exact mode 0600"
      )

      release_link << true
      Timeout.timeout(5) { writer_thread.join }
    end
  ensure
    release_link << true if writer_thread&.alive?
    writer_thread&.join(1)
  end

  raise writer_error if writer_error
  assert.call(File.binread(pid_file) == serialized, "published PID record content changed")
  assert.call(
    (File.stat(pid_file).mode & 0o777) == 0o600,
    "published PID record did not have exact mode 0600"
  )
  staging_pattern = File.join(directory, ".#{File.basename(pid_file)}.*.tmp")
  assert.call(Dir.glob(staging_pattern).empty?, "PID staging entry remained after publication")
end

Dir.mktmpdir("headless-service-pid-write-failure") do |directory|
  pid_file = File.join(directory, "service.pid")
  staging_prefix = File.join(directory, ".#{File.basename(pid_file)}.")
  original_open = File.method(:open)
  observed_error = nil

  failing_open = lambda do |*arguments, &block|
    path = arguments.first.to_s
    unless path.start_with?(staging_prefix)
      next original_open.call(*arguments, &block)
    end

    file = PartialWriteFile.new(original_open.call(*arguments))
    if block
      begin
        block.call(file)
      ensure
        file.close unless file.closed?
      end
    else
      file
    end
  end

  File.stub(:open, failing_open) do
    begin
      writer.write_pid_record(pid_file, record)
    rescue TextStatsService::ConfigurationError => error
      observed_error = error
    end
  end

  assert.call(observed_error, "injected partial PID-record write did not fail")
  assert.call(
    !File.exist?(pid_file) && !File.symlink?(pid_file),
    "partial PID record was exposed at the final pathname"
  )
  staging_pattern = File.join(directory, ".#{File.basename(pid_file)}.*.tmp")
  assert.call(Dir.glob(staging_pattern).empty?, "partial PID staging entry was not removed")
end

puts "Atomic PID-record publication tests passed."
