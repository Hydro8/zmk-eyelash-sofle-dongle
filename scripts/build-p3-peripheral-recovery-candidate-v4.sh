#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SIDE="${1:-left}"
case "$SIDE" in
  left) SHIELD='eyelash_sofle_peripheral_left' ;;
  right) SHIELD='eyelash_sofle_peripheral_right' ;;
  *) echo "Usage: $0 [left|right]" >&2; exit 2 ;;
esac

# Start from the clean pinned ZMK baseline and apply/build the proven v3 source shape.
# v4 then changes only the recovery-success criterion: BLE connected() is not enough;
# the guard is released only after a successful split position notification.
bash "$ROOT/scripts/build-p3-peripheral-recovery-candidate-v3.sh" "$SIDE"

python3 - "$ROOT/zmk" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])

def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: expected exactly one source anchor in {path}, got {count}")
    path.write_text(text.replace(old, new, 1))

header = root / "app/src/split/bluetooth/peripheral.h"
replace_once(header,
    "void zmk_split_bt_peripheral_request_recovery(void);\nstruct zmk_split_transport_peripheral *zmk_split_transport_peripheral_bt(void);",
    "void zmk_split_bt_peripheral_request_recovery(void);\nvoid zmk_split_bt_peripheral_mark_transport_ready(void);\nstruct zmk_split_transport_peripheral *zmk_split_transport_peripheral_bt(void);")

peripheral = root / "app/src/split/bluetooth/peripheral.c"
replace_once(peripheral,
    '''static void connected(struct bt_conn *conn, uint8_t err) {\n    is_connected = (err == 0);\n    if (is_connected && recovery_in_progress) {\n        k_work_cancel_delayable(&recovery_guard_timeout);\n        recovery_in_progress = false;\n        LOG_WRN("P3 recovery v3: split connection recovered");\n    }''',
    '''static void connected(struct bt_conn *conn, uint8_t err) {\n    is_connected = (err == 0);''')

text = peripheral.read_text()
anchor = "void zmk_split_bt_peripheral_request_recovery(void) {\n"
idx = text.find(anchor)
if idx < 0:
    raise SystemExit("ERROR: request_recovery anchor missing")
mark_fn = '''void zmk_split_bt_peripheral_mark_transport_ready(void) {\n    if (!recovery_in_progress) {\n        return;\n    }\n\n    k_work_cancel_delayable(&recovery_guard_timeout);\n    recovery_in_progress = false;\n    LOG_WRN("P3 recovery v4: split transport ready after successful notification");\n}\n\n'''
peripheral.write_text(text[:idx] + mark_fn + text[idx:])

service = root / "app/src/split/bluetooth/service.c"
replace_once(service,
    '''        int err = bt_gatt_notify(NULL, &split_svc.attrs[1], &state, sizeof(state));\n        if (err) {\n            LOG_DBG("Error notifying %d", err);\n            if (err == -ENOTCONN) {\n                zmk_split_bt_peripheral_request_recovery();\n            }\n        }''',
    '''        int err = bt_gatt_notify(NULL, &split_svc.attrs[1], &state, sizeof(state));\n        if (!err) {\n            zmk_split_bt_peripheral_mark_transport_ready();\n        }\n        if (err) {\n            LOG_DBG("Error notifying %d", err);\n            if (err == -ENOTCONN) {\n                zmk_split_bt_peripheral_request_recovery();\n            }\n        }''')
print("P3 recovery candidate v4 source edits applied")
PY

git -C "$ROOT/zmk" diff --check
BUILD_DIR="$ROOT/build/p3-peripheral-${SIDE}-recovery-v4"
west build -s zmk/app -b 'nice_nano@2' --pristine -d "$BUILD_DIR" --snippet zmk-usb-logging -- \
  "-DBOARD_ROOT=$ROOT" \
  "-DZMK_CONFIG=$ROOT/config" \
  "-DEXTRA_CONF_FILE=$ROOT/config/p3-peripheral-recovery-debug.conf" \
  "-DCMAKE_PREFIX_PATH=$ROOT/zephyr/share/zephyr-package" \
  "-DSHIELD=$SHIELD"

test -f "$BUILD_DIR/zephyr/zmk.uf2"
echo "PASS: P3 peripheral $SIDE recovery candidate v4 built"
echo "UF2: $BUILD_DIR/zephyr/zmk.uf2"
