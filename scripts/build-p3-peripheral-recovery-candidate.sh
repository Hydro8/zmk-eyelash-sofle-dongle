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

# west update restores the exact pinned ZMK revision. Apply the candidate
# changes with exact source anchors so a malformed patch cannot hide a drift
# in the upstream baseline. Every replacement is fail-closed.
python3 - "$ROOT/zmk" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: expected exactly one source anchor in {path}, got {count}")
    path.write_text(text.replace(old, new, 1))

header = root / "app/src/split/bluetooth/peripheral.h"
replace_once(
    header,
    "#include <zmk/split/transport/peripheral.h>\n\nstruct zmk_split_transport_peripheral *zmk_split_transport_peripheral_bt(void);",
    "#include <zmk/split/transport/peripheral.h>\n\nvoid zmk_split_bt_peripheral_request_recovery(void);\nstruct zmk_split_transport_peripheral *zmk_split_transport_peripheral_bt(void);",
)

peripheral = root / "app/src/split/bluetooth/peripheral.c"
replace_once(
    peripheral,
    "static bool low_duty_advertising = false;\nstatic bool enabled = false;",
    "static bool low_duty_advertising = false;\nstatic bool enabled = false;\nstatic bool recovery_in_progress = false;",
)
replace_once(
    peripheral,
    "K_WORK_DEFINE(advertising_work, advertising_cb);\n\nstatic void connected(struct bt_conn *conn, uint8_t err) {",
    '''K_WORK_DEFINE(advertising_work, advertising_cb);\n\nstatic void find_first_conn(struct bt_conn *conn, void *data);\n\nstatic void recovery_work_cb(struct k_work *work) {\n    if (!enabled) {\n        recovery_in_progress = false;\n        return;\n    }\n\n    struct bt_conn *conn = NULL;\n    bt_conn_foreach(BT_CONN_TYPE_LE, find_first_conn, &conn);\n\n    if (conn) {\n        int err = bt_conn_disconnect(conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);\n        if (err == 0) {\n            LOG_WRN("P3 recovery: disconnecting stale split connection");\n            return;\n        }\n        if (err != -ENOTCONN) {\n            LOG_WRN("P3 recovery: stale disconnect failed (%d)", err);\n            recovery_in_progress = false;\n            return;\n        }\n    }\n\n    low_duty_advertising = false;\n    LOG_WRN("P3 recovery: restarting directed advertising");\n    k_work_submit(&advertising_work);\n}\n\nK_WORK_DEFINE(recovery_work, recovery_work_cb);\n\nstatic void connected(struct bt_conn *conn, uint8_t err) {''',
)
replace_once(
    peripheral,
    "static void connected(struct bt_conn *conn, uint8_t err) {\n    is_connected = (err == 0);",
    "static void connected(struct bt_conn *conn, uint8_t err) {\n    is_connected = (err == 0);\n    if (is_connected) {\n        recovery_in_progress = false;\n    }",
)
replace_once(
    peripheral,
    "    is_connected = false;\n\n    raise_zmk_split_peripheral_status_changed(",
    "    is_connected = false;\n    recovery_in_progress = false;\n\n    raise_zmk_split_peripheral_status_changed(",
)
replace_once(
    peripheral,
    "struct zmk_split_transport_peripheral *zmk_split_transport_peripheral_bt(void) {\n    return &bt_peripheral;\n}\n\nstatic void notify_transport_status(void) {",
    '''struct zmk_split_transport_peripheral *zmk_split_transport_peripheral_bt(void) {\n    return &bt_peripheral;\n}\n\nvoid zmk_split_bt_peripheral_request_recovery(void) {\n    if (!enabled || recovery_in_progress) {\n        return;\n    }\n\n    recovery_in_progress = true;\n    k_work_submit(&recovery_work);\n}\n\nstatic void notify_transport_status(void) {''',
)

service = root / "app/src/split/bluetooth/service.c"
replace_once(
    service,
    "#include <zephyr/drivers/sensor.h>",
    "#include <errno.h>\n#include <zephyr/drivers/sensor.h>",
)
replace_once(
    service,
    '''        int err = bt_gatt_notify(NULL, &split_svc.attrs[1], &state, sizeof(state));\n        if (err) {\n            LOG_DBG("Error notifying %d", err);\n        }''',
    '''        int err = bt_gatt_notify(NULL, &split_svc.attrs[1], &state, sizeof(state));\n        if (err) {\n            LOG_DBG("Error notifying %d", err);\n            if (err == -ENOTCONN) {\n                zmk_split_bt_peripheral_request_recovery();\n            }\n        }''',
)

print("P3 recovery candidate source edits applied")
PY

git -C "$ROOT/zmk" diff --check

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
