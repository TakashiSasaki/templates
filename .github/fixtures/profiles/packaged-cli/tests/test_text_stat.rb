# frozen_string_literal: true

require "json"
require "minitest/autorun"
require "open3"
require "rbconfig"
require_relative "../src/text_stat"

class TextStatTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  COMMAND = [RbConfig.ruby, File.join(ROOT, "bin/text-stat")].freeze

  def run_cli(*arguments, stdin_data: "")
    Open3.capture3(*COMMAND, *arguments, stdin_data: stdin_data, chdir: ROOT)
  end

  def assert_json_contract(output, expected_result)
    parsed = JSON.parse(output)
    assert_equal "1", parsed.fetch("contractVersion")
    assert_equal true, parsed.fetch("ok")

    result = parsed.fetch("result")
    assert_kind_of Hash, result
    expected_result.each do |field, expected|
      assert_equal expected, result.fetch(field), "unexpected #{field} result"
    end
  end

  def test_analyze_counts_utf8_bytes_lines_and_words
    assert_equal(
      { "bytes" => 18, "lines" => 2, "words" => 3 },
      TextStat.analyze("alpha βeta\ngamma\n")
    )
  end

  def test_help_and_version
    stdout, stderr, status = run_cli("--help")
    assert status.success?, stderr
    assert_includes stdout, "Usage: text-stat"
    assert_empty stderr

    stdout, stderr, status = run_cli("--version")
    assert status.success?, stderr
    assert_equal "1.0.0\n", stdout
    assert_empty stderr
  end

  def test_human_output_from_standard_input
    stdout, stderr, status = run_cli("-", stdin_data: "one two\n")
    assert status.success?, stderr
    assert_empty stderr
    assert_equal "bytes: 8\nlines: 1\nwords: 2\n", stdout
  end

  def test_json_output_from_standard_input
    stdout, stderr, status = run_cli("--output", "json", "-", stdin_data: "one two\n")
    assert status.success?, stderr
    assert_empty stderr
    assert_json_contract(stdout, "bytes" => 8, "lines" => 1, "words" => 2)
  end

  def test_json_contract_accepts_additive_result_fields
    output = JSON.generate(
      "contractVersion" => "1",
      "ok" => true,
      "result" => { "bytes" => 8, "lines" => 1, "words" => 2, "characters" => 7 }
    )

    assert_json_contract(output, "bytes" => 8, "lines" => 1, "words" => 2)
  end

  def test_json_contract_rejects_a_missing_required_result_field
    output = JSON.generate(
      "contractVersion" => "1",
      "ok" => true,
      "result" => { "bytes" => 8, "lines" => 1 }
    )

    error = assert_raises(KeyError) do
      assert_json_contract(output, "bytes" => 8, "lines" => 1, "words" => 2)
    end
    assert_includes error.message, "words"
  end

  def test_invalid_invocation_uses_exit_code_two
    stdout, stderr, status = run_cli("--output", "yaml", "-")
    assert_equal 2, status.exitstatus
    assert_empty stdout
    refute_empty stderr
  end

  def test_invalid_utf8_uses_exit_code_two
    stdout, stderr, status = run_cli("-", stdin_data: "\xFF".b)
    assert_equal 2, status.exitstatus
    assert_empty stdout
    assert_equal "input is not valid UTF-8\n", stderr
  end

  def test_missing_input_uses_exit_code_three
    stdout, stderr, status = run_cli("missing.txt")
    assert_equal 3, status.exitstatus
    assert_empty stdout
    assert_includes stderr, "unable to read input"
  end
end
