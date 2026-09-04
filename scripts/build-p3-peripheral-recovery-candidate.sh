#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v west >/dev/null 2>&1 || {
  echo "ERROR: west is required" >&2
  exit 2
}

SIDE="${1:-left}"
case "$SIDE" in
  left) SHIELD='eyelash_sofle_peripheral_left' ;;
  right) SHIELD='eyelash_sofle_peripheral_right' ;;
  *) echo "Usage: $0 [left|right]" >&2; exit 2 ;;
esac

if [ ! -d .west ]; then
  west init -l config
fi
west update
west zephyr-export

PATCH="$ROOT/patches/zmk-p3-peripheral-stale-recovery.patch"

# west update restores the exact pinned ZMK revision. Apply the candidate patch
# only to the local workspace used for this dedicated physical qualification.
if git -C "$ROOT/zmk" apply --reverse --check "$PATCH" >/dev/null 2>&1; then
  echo "P3 recovery candidate patch already applied"
else
  git -C "$ROOT/zmk" apply --check "$PATCH"
  git -C "$ROOT/zmk" apply "$PATCH"
  echo "P3 recovery candidate patch applied"
fi

west build \
  -s zmk/app \
  -b 'nice_nano@2' \
  --pristine \
  -d "$ROOT/build/p3-peripheral-${SIDE}-recovery" \
  -S zmk-usb-logging \
  -- \
  "-DBOARD_ROOT=$ROOT" \
  "-DZMK_CONFIG=$ROOT/config" \
  "-DCMAKE_PREFIX_PATH=$ROOT/zephyr/share/zephyr-package" \
  "-DSHIELD=$SHIELD" \
  "-DEXTRA_CONF_FILE=$ROOT/config/p3-peripheral-recovery-debug.conf"

echo "PASS: P3 peripheral ${SIDE} recovery candidate built"
echo "UF2: $ROOT/build/p3-peripheral-${SIDE}-recovery/zephyr/zmk.uf2"
