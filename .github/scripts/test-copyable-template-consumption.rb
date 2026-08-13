#!/usr/bin/env ruby
# frozen_string_literal: true

# Temporary compatibility entry point retained while generated repository policy
# still names the historical Ruby command. The authoritative implementation is
# the Python clean-room harness; preserve its exit status and arguments exactly.
python = ENV.fetch("PYTHON", "python")
script = File.expand_path("test_copyable_template_consumption.py", __dir__)
exec(python, script, *ARGV)
