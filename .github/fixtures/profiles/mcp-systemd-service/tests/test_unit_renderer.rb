# frozen_string_literal: true

require "etc"
require "fileutils"
require "minitest/autorun"
require "rbconfig"
require "tmpdir"
require_relative "../deployment/systemd/render_unit"

class TextStatsMcpSystemdUnitRendererTest < Minitest::Test
  Account = Struct.new(:uid, :gid)
  Group = Struct.new(:gid, :mem)

  ROOT = File.expand_path("..", __dir__)

  def setup
    @directory = Dir.mktmpdir("mcp-systemd-renderer")
    File.chmod(0o755, @directory)
    @skill_root = File.join(@directory, "skill")
    %w[mcp src].each { |relative| FileUtils.mkdir_p(File.join(@skill_root, relative), mode: 0o755) }
    {
      "Gemfile" => "source \"https://rubygems.org\"\n",
      "mcp/http_server.rb" => "# fixture\n",
      "mcp/server_factory.rb" => "# fixture\n",
      "src/text_stats.rb" => "# fixture\n"
    }.each do |relative, content|
      path = File.join(@skill_root, relative)
      File.binwrite(path, content)
      File.chmod(0o644, path)
    end
    File.chmod(0o755, @skill_root)

    @token = File.join(@directory, "token")
    File.binwrite(@token, "fixture-systemd-token-0123456789abcdef\n")
    File.chmod(0o600, @token)

    @runtime_bin = File.join(@directory, "runtime-bin")
    Dir.mkdir(@runtime_bin, 0o755)
    @ruby = File.join(@runtime_bin, "ruby")
    @bundle = File.join(@runtime_bin, "bundle")
    [@ruby, @bundle].each do |path|
      File.binwrite(path, "#!/bin/sh\nexit 0\n")
      File.chmod(0o755, path)
    end

    @account = Account.new(Process.uid + 100_000, Process.gid + 100_000)
    @group = Group.new(@account.gid, ["fixture-user"])
  end

  def teardown
    FileUtils.remove_entry(@directory) if @directory && File.exist?(@directory)
  end

  def options
    {
      service_user: "fixture-user",
      service_group: "fixture-group",
      skill_root: @skill_root,
      token_file: @token,
      runtime_bin_dir: @runtime_bin,
      bundle_path: @bundle,
      port: "4572"
    }
  end

  def with_valid_identity
    renderer = TextStatsMcpSystemd::UnitRenderer
    renderer.stub(:lookup_user, @account) do
      renderer.stub(:lookup_group, @group) do
        renderer.stub(:token_owner_allowed?, true) do
          renderer.stub(:verify_bundler!, nil) { yield }
        end
      end
    end
  end

  def test_renders_fixed_service_contract
    rendered = nil
    with_valid_identity { rendered = TextStatsMcpSystemd::UnitRenderer.render(options) }

    refute_includes rendered, "@@"
    assert_includes rendered, "Type=notify"
    assert_includes rendered, "NotifyAccess=main"
    assert_includes rendered, "User=fixture-user"
    assert_includes rendered, "Group=fixture-group"
    assert_includes rendered, "WorkingDirectory=#{@skill_root}"
    assert_includes rendered, "LoadCredential=text-stats-mcp-token:#{@token}"
    assert_includes rendered, "ExecStart=#{@bundle} exec ruby mcp/http_server.rb"
    assert_includes rendered, "Restart=on-failure"
    assert_includes rendered, "RestartPreventExitStatus=78"
    assert_includes rendered, "KillMode=control-group"
    assert_includes rendered, "ProtectSystem=strict"
    assert_includes rendered, "CapabilityBoundingSet=\n"
    refute_includes rendered, "0.0.0.0"
  end

  def test_preserves_account_and_group_lookup_diagnostics
    missing_user = "missing-user-#{Process.pid}"
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.lookup_user(missing_user)
    end
    assert_equal "service user does not exist: #{missing_user}", error.message

    missing_group = "missing-group-#{Process.pid}"
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.lookup_group(missing_group)
    end
    assert_equal "service group does not exist: #{missing_group}", error.message
  end

  def test_rejects_privileged_user_and_group
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.validate_service_identity!(
        Account.new(0, 1000),
        Group.new(1000, []),
        "fixture-user"
      )
    end
    assert_includes error.message, "service user"

    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.validate_service_identity!(
        Account.new(1000, 1000),
        Group.new(0, ["fixture-user"]),
        "fixture-user"
      )
    end
    assert_includes error.message, "service group"
  end

  def test_accepts_only_root_or_service_user_token_ownership
    assert TextStatsMcpSystemd::UnitRenderer.token_owner_allowed?(0, @account.uid)
    assert TextStatsMcpSystemd::UnitRenderer.token_owner_allowed?(@account.uid, @account.uid)
    refute TextStatsMcpSystemd::UnitRenderer.token_owner_allowed?(@account.uid + 1, @account.uid)
  end

  def test_rejects_insecure_or_symlinked_token
    File.chmod(0o644, @token)
    error = nil
    with_valid_identity do
      error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
        TextStatsMcpSystemd::UnitRenderer.render(options)
      end
    end
    assert_includes error.message, "0600"

    File.chmod(0o600, @token)
    link = File.join(@directory, "token-link")
    File.symlink(@token, link)
    with_valid_identity do
      error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
        TextStatsMcpSystemd::UnitRenderer.render(options.merge(token_file: link))
      end
      assert_includes error.message, "non-symlink"
    end
  end

  def test_rejects_mutable_skill_and_runtime_inputs
    File.chmod(0o666, File.join(@skill_root, "mcp/http_server.rb"))
    with_valid_identity do
      error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
        TextStatsMcpSystemd::UnitRenderer.render(options)
      end
      assert_includes error.message, "service identity can modify skill root"
    end

    File.chmod(0o644, File.join(@skill_root, "mcp/http_server.rb"))
    File.chmod(0o777, @runtime_bin)
    with_valid_identity do
      error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
        TextStatsMcpSystemd::UnitRenderer.render(options)
      end
      assert_includes error.message, "runtime bin directory"
    end
  end

  def test_treats_service_owned_paths_as_mutable_even_without_write_bit
    File.chmod(0o555, @skill_root)
    stat = File.stat(@skill_root)
    assert TextStatsMcpSystemd::UnitRenderer.identity_can_modify?(stat, stat.uid, [stat.gid])
  end

  def test_verifies_selected_executable_is_bundler
    ruby_path = File.realpath(RbConfig.ruby)
    bundle_path = File.realpath(Gem.bin_path("bundler", "bundle"))
    TextStatsMcpSystemd::UnitRenderer.verify_bundler!(ruby_path, bundle_path)

    fake = File.join(@directory, "fake-bundle")
    File.binwrite(fake, "#!/bin/sh\nexit 0\n")
    File.chmod(0o755, fake)
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.verify_bundler!(ruby_path, fake)
    end
    assert_includes error.message, "is not Bundler"
  end

  def test_rejects_path_injection_invalid_port_and_missing_ruby
    with_valid_identity do
      error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
        TextStatsMcpSystemd::UnitRenderer.render(options.merge(skill_root: "."))
      end
      assert_includes error.message, "absolute"

      error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
        TextStatsMcpSystemd::UnitRenderer.render(options.merge(port: "not-a-port"))
      end
      assert_includes error.message, "base-10 integer"

      File.unlink(@ruby)
      error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
        TextStatsMcpSystemd::UnitRenderer.render(options)
      end
      assert_includes error.message, "ruby executable does not exist"
    end
  end

  def test_output_writer_uses_exact_mode_and_refuses_replacement_paths
    output = File.join(@directory, "rendered.service")
    previous = File.umask(0o0777)
    TextStatsMcpSystemd::UnitRenderer.write_output!(output, "unit\n")
    File.umask(previous)
    assert_equal 0o644, File.stat(output).mode & 0o777
    assert_raises(Errno::EEXIST) do
      TextStatsMcpSystemd::UnitRenderer.write_output!(output, "replacement\n")
    end

    real_parent = File.join(@directory, "real-parent")
    Dir.mkdir(real_parent)
    linked_parent = File.join(@directory, "linked-parent")
    File.symlink(real_parent, linked_parent)
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.validate_output_path!(File.join(linked_parent, "unit.service"))
    end
    assert_includes error.message, "output parent"
  ensure
    File.umask(previous) if previous
  end
end
