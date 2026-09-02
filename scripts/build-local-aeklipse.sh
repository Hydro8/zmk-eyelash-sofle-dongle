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

COMMON=(
  -s zmk/app
  -b 'nice_nano@2'
  --pristine
  --
  "-DBOARD_ROOT=$ROOT"
  "-DZMK_CONFIG=$ROOT/config"
  "-DCMAKE_PREFIX_PATH=$ROOT/zephyr/share/zephyr-package"
)

build_target() {
  local name="$1"
  local shields="$2"
  echo "== BUILD $name =="
  west build "${COMMON[@]}" -d "$ROOT/build/$name" "-DSHIELD=$shields"
}

build_target settings-reset 'settings_reset'
build_target central-dongle 'eyelash_sofle_central_dongle dongle_display raw_hid_adapter'
build_target peripheral-left 'eyelash_sofle_peripheral_left'
build_target peripheral-right 'eyelash_sofle_peripheral_right'

echo "PASS: four Selenium targets built locally outside GitHub Actions"
