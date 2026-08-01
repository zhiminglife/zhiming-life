#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 SIDECAR RESOURCE_DIR DMG" >&2
  exit 2
fi

sidecar=$1
resource_dir=$2
dmg=$3
temp_root=$(mktemp -d "${RUNNER_TEMP:-/tmp}/zhiming-macos-smoke.XXXXXX")
data_dir="$temp_root/data"
mount_dir="$temp_root/mount"
sidecar_log="$temp_root/sidecar.log"
port=18767
token=macos-sidecar-smoke
parent_pid=""
sidecar_pid=""
app_pid=""
packaged_sidecar_pids=""
mounted=false

cleanup() {
  if [[ -n "$parent_pid" ]] && kill -0 "$parent_pid" 2>/dev/null; then
    kill "$parent_pid" 2>/dev/null || true
  fi
  if [[ -n "$sidecar_pid" ]] && kill -0 "$sidecar_pid" 2>/dev/null; then
    kill "$sidecar_pid" 2>/dev/null || true
  fi
  if [[ -n "$app_pid" ]] && kill -0 "$app_pid" 2>/dev/null; then
    kill "$app_pid" 2>/dev/null || true
  fi
  for pid in $packaged_sidecar_pids; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  if [[ "$mounted" == true ]]; then
    if hdiutil detach "$mount_dir" -force -quiet; then
      mounted=false
    fi
  fi
  if [[ "$mounted" == false ]]; then
    rm -rf "$temp_root"
  fi
}
trap cleanup EXIT

test -x "$sidecar"
test -d "$resource_dir/models/embedding"
test -d "$resource_dir/models/reranker"
test -f "$resource_dir/seeds/knowledge.sqlite"
test -f "$resource_dir/seeds/cases.sqlite"
[[ " $(lipo -archs "$sidecar") " == *" arm64 "* ]]

mkdir -p "$data_dir" "$mount_dir"
sleep 300 &
parent_pid=$!

ZHIMING_LIFE_API_PORT=$port \
ZHIMING_LIFE_API_TOKEN=$token \
ZHIMING_LIFE_DATA_DIR=$data_dir \
ZHIMING_LIFE_RESOURCE_DIR=$resource_dir \
ZHIMING_LIFE_PARENT_PID=$parent_pid \
  "$sidecar" >"$sidecar_log" 2>&1 &
sidecar_pid=$!

health=""
for _ in $(seq 1 60); do
  if health=$(curl -fsS --max-time 2 "http://127.0.0.1:$port/api/health" 2>/dev/null); then
    break
  fi
  if ! kill -0 "$sidecar_pid" 2>/dev/null; then
    cat "$sidecar_log" >&2
    echo "Frozen sidecar exited before becoming healthy" >&2
    exit 1
  fi
  sleep 2
done

printf '%s' "$health" | python3 -c 'import json, sys; assert json.load(sys.stdin)["status"] == "ok"'

libraries=$(curl -fsS --max-time 10 \
  -H "X-Zhiming-Token: $token" \
  "http://127.0.0.1:$port/api/libraries")
printf '%s' "$libraries" | python3 -c '
import json, sys
items = {item["kind"]: item for item in json.load(sys.stdin)}
assert set(items) == {"knowledge", "cases"}
for kind in ("knowledge", "cases"):
    assert items[kind]["vector_backend"] == "sqlite-vec"
    assert items[kind]["source_count"] >= 1
'

for kind in knowledge cases; do
  hits=$(curl -fsS --max-time 120 --get \
    -H "X-Zhiming-Token: $token" \
    --data-urlencode "q=事业" \
    --data-urlencode "limit=2" \
    "http://127.0.0.1:$port/api/libraries/$kind/search")
  printf '%s' "$hits" | python3 -c 'import json, sys; assert len(json.load(sys.stdin)) >= 1'
done

cors_headers=$(curl -fsS -D - -o /dev/null --max-time 10 -X OPTIONS \
  -H "Origin: tauri://localhost" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: x-zhiming-token" \
  "http://127.0.0.1:$port/api/libraries")
printf '%s' "$cors_headers" | tr -d '\r' | grep -qi '^access-control-allow-origin: tauri://localhost$'

kill "$parent_pid"
wait "$parent_pid" 2>/dev/null || true
parent_pid=""
for _ in $(seq 1 15); do
  if ! kill -0 "$sidecar_pid" 2>/dev/null; then
    break
  fi
  sleep 1
done
if kill -0 "$sidecar_pid" 2>/dev/null; then
  echo "Frozen sidecar remained alive after its parent exited" >&2
  exit 1
fi
wait "$sidecar_pid" 2>/dev/null || true
sidecar_pid=""

hdiutil attach "$dmg" -nobrowse -readonly -mountpoint "$mount_dir"
mounted=true
application=$(find "$mount_dir" -maxdepth 1 -type d -name '*.app' -print -quit)
test -n "$application"

main_binary="$application/Contents/MacOS/zhiming-life-desktop"
bundled_sidecar="$application/Contents/MacOS/zhiming-api"
bundled_resources="$application/Contents/Resources/resources"
test -x "$main_binary"
test -x "$bundled_sidecar"
test -d "$bundled_resources/models/embedding"
test -d "$bundled_resources/models/reranker"
test -f "$bundled_resources/seeds/knowledge.sqlite"
test -f "$bundled_resources/seeds/cases.sqlite"
[[ " $(lipo -archs "$main_binary") " == *" arm64 "* ]]
[[ " $(lipo -archs "$bundled_sidecar") " == *" arm64 "* ]]

open -n "$application"
for _ in $(seq 1 60); do
  app_pid=$(pgrep -x zhiming-life-desktop | tail -n 1 || true)
  if [[ -n "$app_pid" ]]; then
    packaged_sidecar_pids=$(pgrep -P "$app_pid" -x zhiming-api || true)
    if [[ -n "$packaged_sidecar_pids" ]]; then
      break
    fi
  fi
  sleep 2
done
if [[ -z "$app_pid" ]] || [[ -z "$packaged_sidecar_pids" ]]; then
  echo "Packaged application did not start its bundled sidecar" >&2
  exit 1
fi

kill "$app_pid"
wait "$app_pid" 2>/dev/null || true
app_pid=""
for _ in $(seq 1 15); do
  remaining=false
  for pid in $packaged_sidecar_pids; do
    if kill -0 "$pid" 2>/dev/null; then
      remaining=true
    fi
  done
  if [[ "$remaining" == false ]]; then
    packaged_sidecar_pids=""
    break
  fi
  sleep 1
done
if [[ -n "$packaged_sidecar_pids" ]]; then
  echo "Packaged sidecar remained alive after the application exited" >&2
  exit 1
fi
