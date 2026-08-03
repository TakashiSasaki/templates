# frozen_string_literal: true

require "etc"
require "fileutils"
require "minitest/autorun"
require "rbconfig"
require "English"
require "tmpdir"
require_relative "../deployment/systemd/render_unit"

class TextStatsMcpSystemdUnitRendererTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)

  def setup
    @directory = Dir.mktmpdir("mcp-systemd-renderer")
    @token = File.join(@directory, "token")
    File.binwrite(@token, "fixture-systemd-token-0123456789abcdef\n")
    File.chmod(0o600, @token)
    @user = Etc.getpwuid(Process.euid)
    @group = Etc.getgrgid(@user.gid)
    @runtime_bin = File.dirname(RbConfig.ruby)
    @bundle = File.join(@runtime_bin, "bundle")
    @bundle = File.join(@runtime_bin, "ruby") unless File.executable?(@bundle)
    @resolved_bundle = File.realpath(@bundle)
  end

  def teardown
    FileUtils.remove_entry(@directory) if @directory && File.exist?(@directory)
  end

  def options
    {
      service_user: @user.name,
      service_group: @group.name,
      skill_root: ROOT,
      token_file: @token,
      runtime_bin_dir: @runtime_bin,
      bundle_path: @bundle,
      port: "4572"
    }
  end

  def test_renders_fixed_service_contract
    rendered = TextStatsMcpSystemd::UnitRenderer.render(options)

    refute_includes rendered, "@@"
    assert_includes rendered, "Type=notify"
    assert_includes rendered, "NotifyAccess=main"
    assert_includes rendered, "User=#{@user.name}"
    assert_includes rendered, "Group=#{@group.name}"
    assert_includes rendered, "WorkingDirectory=#{ROOT}"
    assert_includes rendered, "LoadCredential=text-stats-mcp-token:#{@token}"
    assert_includes rendered, "ExecStart=#{@resolved_bundle} exec ruby mcp/http_server.rb"
    assert_includes rendered, "Restart=on-failure"
    assert_includes rendered, "RestartPreventExitStatus=78"
    assert_includes rendered, "KillMode=control-group"
    assert_includes rendered, "ProtectSystem=strict"
    assert_includes rendered, "CapabilityBoundingSet=\n"
    refute_includes rendered, "0.0.0.0"
  end

  def test_accepts_only_root_or_service_user_token_ownership
    assert TextStatsMcpSystemd::UnitRenderer.token_owner_allowed?(0, @user.uid)
    assert TextStatsMcpSystemd::UnitRenderer.token_owner_allowed?(@user.uid, @user.uid)
    refute TextStatsMcpSystemd::UnitRenderer.token_owner_allowed?(@user.uid + 1, @user.uid)
  end

  def test_rejects_insecure_or_symlinked_token
    File.chmod(0o644, @token)
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.render(options)
    end
    assert_includes error.message, "0600"

    File.chmod(0o600, @token)
    link = File.join(@directory, "token-link")
    File.symlink(@token, link)
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.render(options.merge(token_file: link))
    end
    assert_includes error.message, "non-symlink"
  end

  def test_rejects_path_identity_and_privilege_escalation
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.render(options.merge(service_user: "bad\nUser=root"))
    end
    assert_includes error.message, "unsafe name"

    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.render(options.merge(skill_root: "."))
    end
    assert_includes error.message, "absolute"

    root = Etc.getpwnam("root")
    root_group = Etc.getgrgid(root.gid)
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.render(
        options.merge(service_user: root.name, service_group: root_group.name)
      )
    end
    assert_includes error.message, "unprivileged"
  end

  def test_rejects_invalid_or_incomplete_runtime_selection
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.render(options.merge(port: "0"))
    end
    assert_includes error.message, "between 1 and 65535"

    outside = File.join(@directory, "bundle")
    File.binwrite(outside, "#!/bin/sh\nexit 0\n")
    File.chmod(0o755, outside)
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.render(options.merge(bundle_path: outside))
    end
    assert_includes error.message, "runtime bin directory"

    incomplete_runtime = File.join(@directory, "runtime-bin")
    Dir.mkdir(incomplete_runtime)
    incomplete_bundle = File.join(incomplete_runtime, "bundle")
    File.binwrite(incomplete_bundle, "#!/bin/sh\nexit 0\n")
    File.chmod(0o755, incomplete_bundle)
    error = assert_raises(TextStatsMcpSystemd::UnitRenderer::ConfigurationError) do
      TextStatsMcpSystemd::UnitRenderer.render(
        options.merge(runtime_bin_dir: incomplete_runtime, bundle_path: incomplete_bundle)
      )
    end
    assert_includes error.message, "ruby executable does not exist"
  end

  def test_cli_writes_exact_mode_and_rejects_symlinked_output_parent
    output = File.join(@directory, "rendered.service")
    command = [
      RbConfig.ruby,
      File.join(ROOT, "deployment/systemd/render_unit.rb"),
      "--service-user", @user.name,
      "--service-group", @group.name,
      "--skill-root", ROOT,
      "--token-file", @token,
      "--runtime-bin-dir", @runtime_bin,
      "--bundle-path", @bundle,
      "--port", "4572",
      "--output", output
    ]
    previous = File.umask(0o0777)
    system(*command, out: File::NULL, err: File::NULL)
    File.umask(previous)
    assert $CHILD_STATUS.success?
    assert_equal 0o644, File.stat(output).mode & 0o777

    real_parent = File.join(@directory, "real-parent")
    Dir.mkdir(real_parent)
    linked_parent = File.join(@directory, "linked-parent")
    File.symlink(real_parent, linked_parent)
    linked_output = File.join(linked_parent, "unit.service")
    refute system(*command[0...-1], linked_output, out: File::NULL, err: File::NULL)
    refute File.exist?(File.join(real_parent, "unit.service"))
  ensure
    File.umask(previous) if previous
  end
end
