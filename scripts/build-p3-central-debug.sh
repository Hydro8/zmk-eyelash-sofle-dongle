#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v west >/dev/null 2>&1 || {
  echo "ERROR: west is required" >&2
  exit 2
}

if [ ! -d .west ]; then
  west init -l config
fi
west update
west zephyr-export

west build \
  -s zmk/app \
  -b 'nice_nano@2' \
  --pristine \
  -d "$ROOT/build/p3-central-debug" \
  -- \
  "-DBOARD_ROOT=$ROOT" \
  "-DZMK_CONFIG=$ROOT/config" \
  "-DCMAKE_PREFIX_PATH=$ROOT/zephyr/share/zephyr-package" \
  "-DSHIELD=eyelash_sofle_central_dongle dongle_display raw_hid_adapter" \
  "-DEXTRA_CONF_FILE=$ROOT/config/p3-central-debug.conf"

echo "PASS: P3 central diagnostic firmware built"
echo "UF2: $ROOT/build/p3-central-debug/zephyr/zmk.uf2"
