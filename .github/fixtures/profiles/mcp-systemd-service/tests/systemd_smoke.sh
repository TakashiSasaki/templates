#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SERVICE_ID="textstats${GITHUB_RUN_ID:-local}${GITHUB_RUN_ATTEMPT:-1}$$"
SERVICE_USER=${SERVICE_ID:0:31}
SERVICE_GROUP=$SERVICE_USER
INSTALL_ROOT="/usr/local/lib/text-stats-mcp-$SERVICE_USER"
RUNTIME_BIN_DIR=$(dirname "$(ruby -e 'print File.realpath(RbConfig.ruby)')")
BUNDLE_PATH=$(command -v bundle)
PORT=$(ruby -rsocket -e 's=TCPServer.new("127.0.0.1",0); print s.addr[1]; s.close')
TOKEN_DIR=$(mktemp -d)
MODE_STATE="$TOKEN_DIR/path-modes"
CLIENT_TOKEN_FILE="$TOKEN_DIR/client-token"
TOKEN_SOURCE_FILE="$TOKEN_DIR/source-token"
RESIST_PARENT_FILE="/run/$SERVICE_USER-resistant-parent.pid"
RESIST_CHILD_FILE="/run/$SERVICE_USER-resistant-child.pid"
RESIST_LAUNCHER=0
UNIT_NAME="$SERVICE_USER.service"
UNIT_TMP="$TOKEN_DIR/$UNIT_NAME"
UNIT_PATH="/etc/systemd/system/$UNIT_NAME"
TOKEN_VALUE='fixture-systemd-token-0123456789abcdef'
printf '%s\n' "$TOKEN_VALUE" > "$CLIENT_TOKEN_FILE"
chmod 0600 "$CLIENT_TOKEN_FILE"

cleanup() {
  set +e
  if [[ "$RESIST_LAUNCHER" =~ ^[0-9]+$ && "$RESIST_LAUNCHER" -gt 0 ]]; then
    kill -KILL "$RESIST_LAUNCHER" >/dev/null 2>&1 || true
    wait "$RESIST_LAUNCHER" >/dev/null 2>&1 || true
  fi
  sudo systemctl stop "$UNIT_NAME" >/dev/null 2>&1 || true
  sudo rm -f "$UNIT_PATH" "$RESIST_PARENT_FILE" "$RESIST_CHILD_FILE"
  sudo systemctl daemon-reload >/dev/null 2>&1 || true
  sudo rm -rf "$INSTALL_ROOT"
  if [[ -f "$MODE_STATE" ]]; then
    while IFS=$'\t' read -r mode path; do
      sudo chmod "$mode" "$path" >/dev/null 2>&1 || true
    done < <(tac "$MODE_STATE")
  fi
  sudo userdel "$SERVICE_USER" >/dev/null 2>&1 || true
  rm -rf "$TOKEN_DIR"
}

diagnose_failure() {
  status=$?
  trap - ERR
  set +e
  echo "systemd MCP lifecycle smoke failed with status $status" >&2
  sudo systemctl status "$UNIT_NAME" --no-pager --full 2>&1 | sed "s/${TOKEN_VALUE}/[REDACTED]/g" >&2
  sudo journalctl -u "$UNIT_NAME" --no-pager --all 2>&1 | sed "s/${TOKEN_VALUE}/[REDACTED]/g" >&2
  exit "$status"
}

assert_property() {
  property=$1
  expected=$2
  actual=$(sudo systemctl show -p "$property" --value "$UNIT_NAME")
  if [[ "$actual" != "$expected" ]]; then
    echo "expected $property=$expected, got $actual" >&2
    return 1
  fi
}

assert_empty_property() {
  property=$1
  actual=$(sudo systemctl show -p "$property" --value "$UNIT_NAME")
  if [[ -n "$actual" ]]; then
    echo "expected empty $property, got $actual" >&2
    return 1
  fi
}

harden_path_chain() {
  path=$(realpath "$1")
  while [[ "$path" != "/" ]]; do
    if ! grep -Fq $'\t'"$path" "$MODE_STATE" 2>/dev/null; then
      printf '%s\t%s\n' "$(stat -c %a "$path")" "$path" >> "$MODE_STATE"
    fi
    sudo chmod go-w "$path"
    path=$(dirname "$path")
  done
}

assert_zero_status_field() {
  field=$1
  pid=$2
  value=$(awk -v field="$field" '$1 == field ":" { print $2 }' "/proc/$pid/status")
  if [[ -z "$value" || ! "$value" =~ ^0+$ ]]; then
    echo "expected zero $field for PID $pid, got $value" >&2
    return 1
  fi
}

wait_for_file() {
  path=$1
  for _ in $(seq 1 50); do
    [[ -s "$path" ]] && return 0
    sleep 0.1
  done
  echo "timed out waiting for $path" >&2
  return 1
}

assert_terminated() {
  pid=$1
  for _ in $(seq 1 50); do
    if ! sudo kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    state=$(sudo awk '{ print $3 }' "/proc/$pid/stat" 2>/dev/null || true)
    if [[ "$state" == "Z" ]]; then
      return 0
    fi
    sleep 0.1
  done
  state=$(sudo awk '{ print $3 }' "/proc/$pid/stat" 2>/dev/null || true)
  echo "expected PID $pid to be gone or zombie after SIGKILL, state=$state" >&2
  return 1
}

trap diagnose_failure ERR
trap cleanup EXIT

harden_path_chain "$RUNTIME_BIN_DIR"
harden_path_chain "$BUNDLE_PATH"
sudo useradd --system --user-group --no-create-home --home-dir /nonexistent \
  --shell /usr/sbin/nologin "$SERVICE_USER"
sudo install -d -o root -g root -m 0755 "$INSTALL_ROOT"
sudo cp -a "$ROOT/." "$INSTALL_ROOT/"
sudo chown -R root:root "$INSTALL_ROOT"
sudo find "$INSTALL_ROOT" -type d -exec chmod u=rwx,go=rx {} +
sudo find "$INSTALL_ROOT" -type f -perm /111 -exec chmod 0755 {} +
sudo find "$INSTALL_ROOT" -type f ! -perm /111 -exec chmod 0644 {} +
printf '%s\n' "$TOKEN_VALUE" | sudo tee "$TOKEN_SOURCE_FILE" >/dev/null
sudo chown root:root "$TOKEN_SOURCE_FILE"
sudo chmod 0600 "$TOKEN_SOURCE_FILE"

bundle exec ruby deployment/systemd/render_unit.rb \
  --service-user "$SERVICE_USER" \
  --service-group "$SERVICE_GROUP" \
  --skill-root "$INSTALL_ROOT" \
  --token-file "$TOKEN_SOURCE_FILE" \
  --runtime-bin-dir "$RUNTIME_BIN_DIR" \
  --bundle-path "$BUNDLE_PATH" \
  --port "$PORT" \
  --output "$UNIT_TMP"

systemd-analyze verify "$UNIT_TMP"
sudo install -o root -g root -m 0644 "$UNIT_TMP" "$UNIT_PATH"
sudo systemctl daemon-reload
sudo systemctl start "$UNIT_NAME"
sudo systemctl is-active --quiet "$UNIT_NAME"

TEXT_STATS_MCP_HTTP_PORT="$PORT" TEXT_STATS_MCP_SMOKE_TOKEN_FILE="$CLIENT_TOKEN_FILE" \
  bundle exec ruby tests/systemd_smoke_client.rb

FIRST_PID=$(sudo systemctl show -p MainPID --value "$UNIT_NAME")
[[ "$FIRST_PID" != "0" ]]
assert_property User "$SERVICE_USER"
assert_property Group "$SERVICE_GROUP"
assert_property NoNewPrivileges yes
assert_property PrivateTmp yes
assert_property PrivateDevices yes
assert_property ProtectSystem strict
assert_property ProtectHome read-only
assert_property ProtectKernelTunables yes
assert_property ProtectKernelModules yes
assert_property ProtectControlGroups yes
assert_property RestrictSUIDSGID yes
assert_property LockPersonality yes
assert_property KillMode control-group
assert_property UMask 0077
assert_empty_property CapabilityBoundingSet
assert_empty_property AmbientCapabilities
ADDRESS_FAMILIES=$(sudo systemctl show -p RestrictAddressFamilies --value "$UNIT_NAME")
if [[ " $ADDRESS_FAMILIES " != *" AF_UNIX "* || " $ADDRESS_FAMILIES " != *" AF_INET "* || $(wc -w <<<"$ADDRESS_FAMILIES") -ne 2 ]]; then
  echo "expected RestrictAddressFamilies to contain only AF_UNIX and AF_INET, got $ADDRESS_FAMILIES" >&2
  exit 1
fi
NO_NEW_PRIVS=$(awk '$1 == "NoNewPrivs:" { print $2 }' "/proc/$FIRST_PID/status")
if [[ "$NO_NEW_PRIVS" != "1" ]]; then
  echo "expected NoNewPrivs=1 for PID $FIRST_PID, got $NO_NEW_PRIVS" >&2
  exit 1
fi
assert_zero_status_field CapEff "$FIRST_PID"
assert_zero_status_field CapAmb "$FIRST_PID"
SERVICE_MOUNT_NS=$(sudo readlink "/proc/$FIRST_PID/ns/mnt")
HOST_MOUNT_NS=$(sudo readlink /proc/1/ns/mnt)
if [[ -z "$SERVICE_MOUNT_NS" || -z "$HOST_MOUNT_NS" || "$SERVICE_MOUNT_NS" == "$HOST_MOUNT_NS" ]]; then
  echo "expected a private mount namespace, service=$SERVICE_MOUNT_NS host=$HOST_MOUNT_NS" >&2
  exit 1
fi

sudo systemctl restart "$UNIT_NAME"
sudo systemctl is-active --quiet "$UNIT_NAME"
SECOND_PID=$(sudo systemctl show -p MainPID --value "$UNIT_NAME")
[[ "$SECOND_PID" != "0" && "$SECOND_PID" != "$FIRST_PID" ]]
TEXT_STATS_MCP_HTTP_PORT="$PORT" TEXT_STATS_MCP_SMOKE_TOKEN_FILE="$CLIENT_TOKEN_FILE" \
  bundle exec ruby tests/systemd_smoke_client.rb

RESTARTS_BEFORE=$(sudo systemctl show -p NRestarts --value "$UNIT_NAME")
sudo kill -KILL "$SECOND_PID"
CURRENT_PID=0
RESTARTS_AFTER=$RESTARTS_BEFORE
ACTIVE_STATE=failed
for _ in $(seq 1 100); do
  CURRENT_PID=$(sudo systemctl show -p MainPID --value "$UNIT_NAME")
  RESTARTS_AFTER=$(sudo systemctl show -p NRestarts --value "$UNIT_NAME")
  ACTIVE_STATE=$(sudo systemctl show -p ActiveState --value "$UNIT_NAME")
  if [[ "$CURRENT_PID" != "0" && "$CURRENT_PID" != "$SECOND_PID" && "$RESTARTS_AFTER" -gt "$RESTARTS_BEFORE" && "$ACTIVE_STATE" == "active" ]]; then
    break
  fi
  sleep 0.1
done
[[ "$ACTIVE_STATE" == "active" ]]
[[ "$CURRENT_PID" != "0" && "$CURRENT_PID" != "$SECOND_PID" ]]
[[ "$RESTARTS_AFTER" -gt "$RESTARTS_BEFORE" ]]
TEXT_STATS_MCP_HTTP_PORT="$PORT" TEXT_STATS_MCP_SMOKE_TOKEN_FILE="$CLIENT_TOKEN_FILE" \
  bundle exec ruby tests/systemd_smoke_client.rb

CONTROL_GROUP=$(sudo systemctl show -p ControlGroup --value "$UNIT_NAME")
[[ -n "$CONTROL_GROUP" && "$CONTROL_GROUP" != "/" ]]
sudo install -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0600 /dev/null "$RESIST_PARENT_FILE"
sudo install -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0600 /dev/null "$RESIST_CHILD_FILE"
sudo -u "$SERVICE_USER" bash -c '
  trap "" TERM INT
  echo $$ > "$1"
  kill -STOP $$
  (
    trap "" TERM INT
    while :; do sleep 1; done
  ) &
  echo $! > "$2"
  wait
' bash "$RESIST_PARENT_FILE" "$RESIST_CHILD_FILE" &
RESIST_LAUNCHER=$!
wait_for_file "$RESIST_PARENT_FILE"
RESIST_PARENT=$(sudo cat "$RESIST_PARENT_FILE")
[[ "$RESIST_PARENT" =~ ^[0-9]+$ ]]
sudo sh -c "echo '$RESIST_PARENT' > '/sys/fs/cgroup${CONTROL_GROUP}/cgroup.procs'"
sudo kill -CONT "$RESIST_PARENT"
wait_for_file "$RESIST_CHILD_FILE"
RESIST_CHILD=$(sudo cat "$RESIST_CHILD_FILE")
[[ "$RESIST_CHILD" =~ ^[0-9]+$ ]]
grep -qx "$RESIST_PARENT" "/sys/fs/cgroup${CONTROL_GROUP}/cgroup.procs"
grep -qx "$RESIST_CHILD" "/sys/fs/cgroup${CONTROL_GROUP}/cgroup.procs"

STOP_STARTED=$(date +%s)
timeout 20s sudo systemctl stop "$UNIT_NAME"
STOP_ELAPSED=$(( $(date +%s) - STOP_STARTED ))
(( STOP_ELAPSED >= 9 ))
! sudo systemctl is-active --quiet "$UNIT_NAME"
assert_terminated "$RESIST_PARENT"
assert_terminated "$RESIST_CHILD"
if [[ -e "/sys/fs/cgroup${CONTROL_GROUP}/cgroup.procs" ]]; then
  [[ -z "$(cat "/sys/fs/cgroup${CONTROL_GROUP}/cgroup.procs")" ]]
fi
kill -TERM "$RESIST_LAUNCHER" >/dev/null 2>&1 || true
wait "$RESIST_LAUNCHER" 2>/dev/null || true
RESIST_LAUNCHER=0

echo "forced control-group shutdown passed"
RESTARTS_BEFORE_CONFIG=$(sudo systemctl show -p NRestarts --value "$UNIT_NAME")
printf '%s\n' 'short' | sudo tee "$TOKEN_SOURCE_FILE" >/dev/null
if sudo systemctl start "$UNIT_NAME"; then
  echo "expected invalid credential content to fail startup" >&2
  exit 1
fi
for _ in $(seq 1 50); do
  STATE=$(sudo systemctl show -p ActiveState --value "$UNIT_NAME")
  [[ "$STATE" == "failed" ]] && break
  sleep 0.1
done
[[ "$STATE" == "failed" ]]
[[ "$(sudo systemctl show -p ExecMainStatus --value "$UNIT_NAME")" == "78" ]]
RESTARTS_AFTER_CONFIG=$(sudo systemctl show -p NRestarts --value "$UNIT_NAME")
[[ "$RESTARTS_AFTER_CONFIG" == "$RESTARTS_BEFORE_CONFIG" ]]

LOGS=$(sudo journalctl -u "$UNIT_NAME" --no-pager)
[[ "$LOGS" != *"$TOKEN_VALUE"* ]]
echo "systemd MCP lifecycle smoke passed"
