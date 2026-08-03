#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SERVICE_USER=$(id -un)
SERVICE_GROUP=$(id -gn)
RUNTIME_BIN_DIR=$(dirname "$(ruby -e 'print RbConfig.ruby')")
BUNDLE_PATH=$(command -v bundle)
PORT=$(ruby -rsocket -e 's=TCPServer.new("127.0.0.1",0); print s.addr[1]; s.close')
TOKEN_DIR=$(mktemp -d)
TOKEN_FILE="$TOKEN_DIR/token"
UNIT_NAME="text-stats-mcp-fixture-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}-$$.service"
UNIT_TMP="$TOKEN_DIR/$UNIT_NAME"
UNIT_PATH="/etc/systemd/system/$UNIT_NAME"
TOKEN_VALUE='fixture-systemd-token-0123456789abcdef'
printf '%s\n' "$TOKEN_VALUE" > "$TOKEN_FILE"
chmod 0600 "$TOKEN_FILE"

cleanup() {
  sudo systemctl stop "$UNIT_NAME" >/dev/null 2>&1 || true
  sudo rm -f "$UNIT_PATH"
  sudo systemctl daemon-reload >/dev/null 2>&1 || true
  rm -rf "$TOKEN_DIR"
}

diagnose_failure() {
  status=$?
  set +e
  echo "systemd MCP lifecycle smoke failed with status $status" >&2
  sudo systemctl status "$UNIT_NAME" --no-pager --full 2>&1 | sed "s/${TOKEN_VALUE}/[REDACTED]/g" >&2
  sudo journalctl -u "$UNIT_NAME" --no-pager --all 2>&1 | sed "s/${TOKEN_VALUE}/[REDACTED]/g" >&2
  exit "$status"
}

trap diagnose_failure ERR
trap cleanup EXIT

bundle exec ruby deployment/systemd/render_unit.rb \
  --service-user "$SERVICE_USER" \
  --service-group "$SERVICE_GROUP" \
  --skill-root "$ROOT" \
  --token-file "$TOKEN_FILE" \
  --runtime-bin-dir "$RUNTIME_BIN_DIR" \
  --bundle-path "$BUNDLE_PATH" \
  --port "$PORT" \
  --output "$UNIT_TMP"

systemd-analyze verify "$UNIT_TMP"
sudo install -o root -g root -m 0644 "$UNIT_TMP" "$UNIT_PATH"
sudo systemctl daemon-reload
sudo systemctl start "$UNIT_NAME"
sudo systemctl is-active --quiet "$UNIT_NAME"

TEXT_STATS_MCP_HTTP_PORT="$PORT" TEXT_STATS_MCP_SMOKE_TOKEN_FILE="$TOKEN_FILE" \
  bundle exec ruby tests/systemd_smoke_client.rb

FIRST_PID=$(sudo systemctl show -p MainPID --value "$UNIT_NAME")
sudo systemctl restart "$UNIT_NAME"
sudo systemctl is-active --quiet "$UNIT_NAME"
SECOND_PID=$(sudo systemctl show -p MainPID --value "$UNIT_NAME")
[[ "$SECOND_PID" != "0" && "$SECOND_PID" != "$FIRST_PID" ]]
TEXT_STATS_MCP_HTTP_PORT="$PORT" TEXT_STATS_MCP_SMOKE_TOKEN_FILE="$TOKEN_FILE" \
  bundle exec ruby tests/systemd_smoke_client.rb

RESTARTS_BEFORE=$(sudo systemctl show -p NRestarts --value "$UNIT_NAME")
sudo kill -KILL "$SECOND_PID"
for _ in $(seq 1 100); do
  CURRENT_PID=$(sudo systemctl show -p MainPID --value "$UNIT_NAME")
  RESTARTS_AFTER=$(sudo systemctl show -p NRestarts --value "$UNIT_NAME")
  if [[ "$CURRENT_PID" != "0" && "$CURRENT_PID" != "$SECOND_PID" && "$RESTARTS_AFTER" -gt "$RESTARTS_BEFORE" ]]; then
    break
  fi
  sleep 0.1
done
sudo systemctl is-active --quiet "$UNIT_NAME"
[[ "$CURRENT_PID" != "0" && "$CURRENT_PID" != "$SECOND_PID" ]]
[[ "$RESTARTS_AFTER" -gt "$RESTARTS_BEFORE" ]]
TEXT_STATS_MCP_HTTP_PORT="$PORT" TEXT_STATS_MCP_SMOKE_TOKEN_FILE="$TOKEN_FILE" \
  bundle exec ruby tests/systemd_smoke_client.rb

sudo systemctl stop "$UNIT_NAME"
! sudo systemctl is-active --quiet "$UNIT_NAME"

RESTARTS_BEFORE_CONFIG=$(sudo systemctl show -p NRestarts --value "$UNIT_NAME")
printf '%s\n' 'short' > "$TOKEN_FILE"
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
