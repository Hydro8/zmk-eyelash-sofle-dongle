#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BUILD_DIR="$ROOT/build/p3-security-key-restore-debug"

west build -s zmk/app -b 'nice_nano@2' --pristine -d "$BUILD_DIR" --snippet zmk-usb-logging -- \
  "-DBOARD_ROOT=$ROOT" \
  "-DZMK_CONFIG=$ROOT/config" \
  "-DEXTRA_CONF_FILE=$ROOT/config/p3-security-key-restore-debug.conf" \
  "-DCMAKE_PREFIX_PATH=$ROOT/zephyr/share/zephyr-package" \
  "-DSHIELD=eyelash_sofle_central_dongle"

test -f "$BUILD_DIR/zephyr/zmk.uf2"
echo "PASS: P3 central SMP/key-restore diagnostic built"
echo "UF2: $BUILD_DIR/zephyr/zmk.uf2"
