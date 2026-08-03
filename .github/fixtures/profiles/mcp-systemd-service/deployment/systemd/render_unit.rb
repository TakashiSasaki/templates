#!/usr/bin/env ruby
# frozen_string_literal: true

require "etc"
require "optparse"
require "pathname"

module TextStatsMcpSystemd
  module UnitRenderer
    PLACEHOLDERS = %w[
      SERVICE_USER
      SERVICE_GROUP
      SKILL_ROOT
      TOKEN_FILE
      RUNTIME_BIN_DIR
      BUNDLE_PATH
      PORT
    ].freeze
    SAFE_NAME = /\A[a-z_][a-z0-9_-]{0,31}\z/
    SAFE_PATH = /\A\/[A-Za-z0-9_+.\/:=@-]+\z/

    class ConfigurationError < StandardError; end

    module_function

    def render(options)
      user = fetch(options, :service_user)
      group = fetch(options, :service_group)
      validate_name!(user, "service user")
      validate_name!(group, "service group")
      account = Etc.getpwnam(user)
      group_record = Etc.getgrnam(group)
      raise ConfigurationError, "service user must be unprivileged" if account.uid.zero?
      unless account.gid == group_record.gid || group_record.mem.include?(user)
        raise ConfigurationError, "service group must contain the service user"
      end

      skill_root = validate_directory!(fetch(options, :skill_root), "skill root")
      %w[Gemfile mcp/http_server.rb mcp/server_factory.rb src/text_stats.rb].each do |relative|
        path = File.join(skill_root, relative)
        raise ConfigurationError, "skill root is missing #{relative}" unless File.file?(path)
      end

      token_file = validate_file!(fetch(options, :token_file), "token file")
      token_stat = File.stat(token_file)
      unless token_owner_allowed?(token_stat.uid, account.uid)
        raise ConfigurationError, "token file must be owned by root or the service user"
      end
      raise ConfigurationError, "token file must have mode 0600 or stricter" unless (token_stat.mode & 0o077).zero?

      runtime_bin_dir = validate_directory!(fetch(options, :runtime_bin_dir), "runtime bin directory")
      ruby_path = validate_file!(File.join(runtime_bin_dir, "ruby"), "ruby executable", allow_final_symlink: true)
      raise ConfigurationError, "ruby executable must be executable" unless File.executable?(ruby_path)
      unless File.dirname(ruby_path) == runtime_bin_dir
        raise ConfigurationError, "ruby executable must resolve inside the runtime bin directory"
      end

      bundle_path = validate_file!(fetch(options, :bundle_path), "bundle executable", allow_final_symlink: true)
      raise ConfigurationError, "bundle executable must be executable" unless File.executable?(bundle_path)
      unless File.dirname(bundle_path) == runtime_bin_dir
        raise ConfigurationError, "bundle executable must be inside the runtime bin directory"
      end

      port = Integer(fetch(options, :port), 10)
      raise ConfigurationError, "port must be between 1 and 65535" unless (1..65_535).cover?(port)

      template = File.binread(File.join(__dir__, "text-stats-mcp.service.in"))
      replacements = {
        "SERVICE_USER" => user,
        "SERVICE_GROUP" => group,
        "SKILL_ROOT" => skill_root,
        "TOKEN_FILE" => token_file,
        "RUNTIME_BIN_DIR" => runtime_bin_dir,
        "BUNDLE_PATH" => bundle_path,
        "PORT" => port.to_s
      }
      PLACEHOLDERS.each { |name| template.gsub!("@@#{name}@@", replacements.fetch(name)) }
      raise ConfigurationError, "rendered unit retains an unresolved placeholder" if template.include?("@@")
      template
    rescue ArgumentError
      raise ConfigurationError, "port must be a base-10 integer between 1 and 65535"
    end

    def token_owner_allowed?(owner_uid, service_uid)
      owner_uid.zero? || owner_uid == service_uid
    end

    def validate_name!(value, label)
      raise ConfigurationError, "#{label} has an unsafe name" unless SAFE_NAME.match?(value)
    end

    def validate_directory!(value, label)
      path = validate_path_syntax!(value, label)
      stat = File.lstat(path)
      raise ConfigurationError, "#{label} must be a non-symlink directory" unless stat.directory?
      raise ConfigurationError, "#{label} must be canonical" unless File.realpath(path) == path
      path
    rescue Errno::ENOENT
      raise ConfigurationError, "#{label} does not exist: #{value}"
    end

    def validate_file!(value, label, allow_final_symlink: false)
      path = validate_path_syntax!(value, label)
      stat = File.lstat(path)
      if stat.symlink?
        raise ConfigurationError, "#{label} must be a regular non-symlink file" unless allow_final_symlink
        path = File.realpath(path)
        stat = File.lstat(path)
      end
      raise ConfigurationError, "#{label} must be a regular non-symlink file" unless stat.file?
      raise ConfigurationError, "#{label} must be canonical" unless File.realpath(path) == path
      path
    rescue Errno::ENOENT
      raise ConfigurationError, "#{label} does not exist: #{value}"
    end

    def validate_path_syntax!(value, label)
      expanded = File.expand_path(value)
      raise ConfigurationError, "#{label} must be absolute" unless Pathname.new(value).absolute?
      raise ConfigurationError, "#{label} contains unsupported characters" unless SAFE_PATH.match?(expanded)
      expanded
    end

    def validate_output_path!(value)
      path = validate_path_syntax!(value, "output")
      parent = File.dirname(path)
      stat = File.lstat(parent)
      raise ConfigurationError, "output parent must be a non-symlink directory" unless stat.directory?
      raise ConfigurationError, "output parent must be canonical" unless File.realpath(parent) == parent
      raise ConfigurationError, "output path already exists" if File.exist?(path) || File.symlink?(path)
      path
    rescue Errno::ENOENT
      raise ConfigurationError, "output parent does not exist: #{parent || value}"
    end

    def fetch(options, key)
      value = options[key]
      raise ConfigurationError, "missing --#{key.to_s.tr("_", "-")}" if value.to_s.empty?
      value
    end
  end
end

if $PROGRAM_NAME == __FILE__
  options = {}
  parser = OptionParser.new do |value|
    value.banner = "Usage: render_unit.rb [options]"
    value.on("--service-user USER") { |item| options[:service_user] = item }
    value.on("--service-group GROUP") { |item| options[:service_group] = item }
    value.on("--skill-root PATH") { |item| options[:skill_root] = item }
    value.on("--token-file PATH") { |item| options[:token_file] = item }
    value.on("--runtime-bin-dir PATH") { |item| options[:runtime_bin_dir] = item }
    value.on("--bundle-path PATH") { |item| options[:bundle_path] = item }
    value.on("--port PORT") { |item| options[:port] = item }
    value.on("--output PATH") { |item| options[:output] = item }
  end

  begin
    parser.parse!
    raise TextStatsMcpSystemd::UnitRenderer::ConfigurationError, "unexpected operands" unless ARGV.empty?
    output = TextStatsMcpSystemd::UnitRenderer.validate_output_path!(
      TextStatsMcpSystemd::UnitRenderer.fetch(options, :output)
    )
    rendered = TextStatsMcpSystemd::UnitRenderer.render(options)
    File.open(output, File::WRONLY | File::CREAT | File::EXCL, 0o600) do |file|
      file.chmod(0o644)
      file.write(rendered)
      file.flush
      file.fsync
    end
  rescue OptionParser::ParseError, TextStatsMcpSystemd::UnitRenderer::ConfigurationError, SystemCallError => error
    warn "render systemd unit failed: #{error.message}"
    exit 78
  end
end
