#!/usr/bin/env ruby
# frozen_string_literal: true

require "etc"
require "find"
require "open3"
require "optparse"
require "pathname"
require "timeout"

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
    REQUIRED_SKILL_FILES = %w[
      Gemfile
      mcp/http_server.rb
      mcp/server_factory.rb
      src/text_stats.rb
    ].freeze
    SAFE_NAME = /\A[a-z_][a-z0-9_-]{0,31}\z/
    SAFE_PATH = /\A\/[A-Za-z0-9_+.\/:=@-]+\z/
    BUNDLER_CHECK_TIMEOUT = 5

    class ConfigurationError < StandardError; end

    module_function

    def render(options)
      user = fetch(options, :service_user)
      group = fetch(options, :service_group)
      validate_name!(user, "service user")
      validate_name!(group, "service group")
      account = lookup_user(user)
      group_record = lookup_group(group)
      validate_service_identity!(account, group_record, user)
      service_gids = service_group_ids(user, account)

      skill_root = validate_directory!(fetch(options, :skill_root), "skill root")
      validate_immutable_tree!(skill_root, account.uid, service_gids, "skill root")
      REQUIRED_SKILL_FILES.each do |relative|
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
      validate_read_only_path!(runtime_bin_dir, account.uid, service_gids, "runtime bin directory")

      ruby_path = validate_file!(File.join(runtime_bin_dir, "ruby"), "ruby executable", allow_final_symlink: true)
      raise ConfigurationError, "ruby executable must be executable" unless File.executable?(ruby_path)
      unless File.dirname(ruby_path) == runtime_bin_dir
        raise ConfigurationError, "ruby executable must resolve inside the runtime bin directory"
      end
      validate_read_only_path!(ruby_path, account.uid, service_gids, "ruby executable")

      bundle_path = validate_file!(fetch(options, :bundle_path), "bundle executable", allow_final_symlink: true)
      raise ConfigurationError, "bundle executable must be executable" unless File.executable?(bundle_path)
      unless File.dirname(bundle_path) == runtime_bin_dir
        raise ConfigurationError, "bundle executable must be inside the runtime bin directory"
      end
      validate_read_only_path!(bundle_path, account.uid, service_gids, "bundle executable")
      verify_bundler!(ruby_path, bundle_path)

      port = parse_port(fetch(options, :port))

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
    end

    def lookup_user(user)
      Etc.getpwnam(user)
    rescue ArgumentError
      raise ConfigurationError, "service user does not exist: #{user}"
    end

    def lookup_group(group)
      Etc.getgrnam(group)
    rescue ArgumentError
      raise ConfigurationError, "service group does not exist: #{group}"
    end

    def validate_service_identity!(account, group_record, user)
      raise ConfigurationError, "service user must be unprivileged" if account.uid.zero?
      raise ConfigurationError, "service group must be unprivileged" if group_record.gid.zero?
      return if account.gid == group_record.gid || group_record.mem.include?(user)

      raise ConfigurationError, "service group must contain the service user"
    end

    def service_group_ids(user, account)
      gids = [account.gid]
      Etc.group { |record| gids << record.gid if record.mem.include?(user) }
      gids.uniq
    end

    def token_owner_allowed?(owner_uid, service_uid)
      owner_uid.zero? || owner_uid == service_uid
    end

    def parse_port(value)
      port = Integer(value, 10)
      raise ConfigurationError, "port must be between 1 and 65535" unless (1..65_535).cover?(port)
      port
    rescue ArgumentError
      raise ConfigurationError, "port must be a base-10 integer between 1 and 65535"
    end

    def verify_bundler!(ruby_path, bundle_path)
      stdout = stderr = nil
      status = nil
      Timeout.timeout(BUNDLER_CHECK_TIMEOUT) do
        stdout, stderr, status = Open3.capture3(
          { "BUNDLE_GEMFILE" => nil, "RUBYOPT" => nil },
          ruby_path,
          bundle_path,
          "--version"
        )
      end
      return if status.success? && stdout.strip.match?(/\ABundler version \d+(?:\.\d+)+\z/)

      detail = stderr.to_s.lines.first.to_s.strip
      suffix = detail.empty? ? "" : ": #{detail}"
      raise ConfigurationError, "bundle executable is not Bundler for the selected Ruby#{suffix}"
    rescue Timeout::Error
      raise ConfigurationError, "Bundler verification timed out"
    rescue SystemCallError => error
      raise ConfigurationError, "unable to verify Bundler: #{error.message}"
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

    def validate_immutable_tree!(root, service_uid, service_gids, label)
      validate_path_chain!(root, service_uid, service_gids, label)
      Find.find(root) do |path|
        stat = File.lstat(path)
        if stat.symlink?
          target = File.realpath(path)
          unless target == root || target.start_with?("#{root}/")
            raise ConfigurationError, "#{label} contains a symlink outside the selected tree: #{path}"
          end
          validate_path_chain!(target, service_uid, service_gids, label)
          next
        end
        unless stat.directory? || stat.file?
          raise ConfigurationError, "#{label} contains an unsupported filesystem entry: #{path}"
        end
        if identity_can_modify?(stat, service_uid, service_gids)
          raise ConfigurationError, "service identity can modify #{label}: #{path}"
        end
      end
    rescue Errno::ENOENT, Errno::EACCES => error
      raise ConfigurationError, "unable to inspect #{label}: #{error.message}"
    end

    def validate_read_only_path!(path, service_uid, service_gids, label)
      validate_path_chain!(path, service_uid, service_gids, label)
      stat = File.stat(path)
      if identity_can_modify?(stat, service_uid, service_gids)
        raise ConfigurationError, "service identity can modify #{label}: #{path}"
      end
      path
    rescue Errno::ENOENT, Errno::EACCES => error
      raise ConfigurationError, "unable to inspect #{label}: #{error.message}"
    end

    def validate_path_chain!(path, service_uid, service_gids, label)
      components = Pathname.new(File.expand_path(path)).ascend.to_a.reverse
      components.each_cons(2) do |parent_path, child_path|
        parent = File.stat(parent_path.to_s)
        child = File.lstat(child_path.to_s)
        next unless identity_can_modify?(parent, service_uid, service_gids)
        next if sticky_parent_protects_child?(parent, child, service_uid)

        raise ConfigurationError, "service identity can replace #{label} through #{parent_path}"
      end
    end

    def sticky_parent_protects_child?(parent, child, service_uid)
      (parent.mode & 0o1000) != 0 && parent.uid != service_uid && child.uid != service_uid
    end

    def identity_can_modify?(stat, service_uid, service_gids)
      stat.uid == service_uid || identity_has_write_bit?(stat, service_uid, service_gids)
    end

    def identity_has_write_bit?(stat, service_uid, service_gids)
      return true if stat.uid == service_uid && (stat.mode & 0o200) != 0
      return true if service_gids.include?(stat.gid) && (stat.mode & 0o020) != 0

      (stat.mode & 0o002) != 0
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

    def write_output!(path, rendered)
      File.open(path, File::WRONLY | File::CREAT | File::EXCL, 0o600) do |file|
        file.chmod(0o644)
        file.write(rendered)
        file.flush
        file.fsync
      end
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
    TextStatsMcpSystemd::UnitRenderer.write_output!(output, rendered)
  rescue OptionParser::ParseError, TextStatsMcpSystemd::UnitRenderer::ConfigurationError, SystemCallError => error
    warn "render systemd unit failed: #{error.message}"
    exit 78
  end
end
