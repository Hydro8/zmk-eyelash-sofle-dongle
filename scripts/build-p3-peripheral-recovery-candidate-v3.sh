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

ZMK_PIN="641514a97db345f499dd50b0360e594270f008fe"
git -C "$ROOT/zmk" reset --hard "$ZMK_PIN"
git -C "$ROOT/zmk" clean -fd
git -C "$ROOT/zmk" diff --quiet
test "$(git -C "$ROOT/zmk" rev-parse HEAD)" = "$ZMK_PIN"
echo "ZMK clean pinned baseline: $ZMK_PIN"

# Candidate v3 is intentionally narrower than v2.
# Demonstrated v2 failure: recycled() cleared recovery_in_progress too early,
# allowing each subsequent -ENOTCONN key event to start another recovery while
# the BLE stack was still recycling/advertising. That caused repeated disconnect
# churn and repeated advertising restart failures.
#
# v3 keeps a single recovery epoch guarded until either:
#   * a real successful BLE connection is observed, or
#   * a bounded 10 s guard timeout expires.
# recycled() requests the normal ZMK advertising work but DOES NOT clear the
# guard. No forced advertising stop/restart is performed.
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
    '''K_WORK_DEFINE(advertising_work, advertising_cb);\n\nstatic void find_first_conn(struct bt_conn *conn, void *data);\n\nstatic void recovery_guard_timeout_cb(struct k_work *work) {\n    if (!recovery_in_progress) {\n        return;\n    }\n\n    if (is_connected) {\n        recovery_in_progress = false;\n        return;\n    }\n\n    LOG_WRN("P3 recovery v3: guard timeout; allowing a later retry");\n    recovery_in_progress = false;\n}\n\nK_WORK_DELAYABLE_DEFINE(recovery_guard_timeout, recovery_guard_timeout_cb);\n\nstatic void recovery_work_cb(struct k_work *work) {\n    if (!enabled) {\n        recovery_in_progress = false;\n        return;\n    }\n\n    struct bt_conn *conn = NULL;\n    bt_conn_foreach(BT_CONN_TYPE_LE, find_first_conn, &conn);\n\n    if (conn) {\n        int err = bt_conn_disconnect(conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);\n        if (err == 0) {\n            LOG_WRN("P3 recovery v3: disconnecting stale split connection");\n            k_work_schedule(&recovery_guard_timeout, K_SECONDS(10));\n            return;\n        }\n        if (err != -ENOTCONN) {\n            LOG_WRN("P3 recovery v3: stale disconnect failed (%d)", err);\n            recovery_in_progress = false;\n            return;\n        }\n    }\n\n    low_duty_advertising = false;\n    k_work_submit(&advertising_work);\n    k_work_schedule(&recovery_guard_timeout, K_SECONDS(10));\n    LOG_WRN("P3 recovery v3: requested normal directed advertising work");\n}\n\nK_WORK_DEFINE(recovery_work, recovery_work_cb);\n\nstatic void connected(struct bt_conn *conn, uint8_t err) {''',
)
replace_once(
    peripheral,
    "static void connected(struct bt_conn *conn, uint8_t err) {\n    is_connected = (err == 0);",
    "static void connected(struct bt_conn *conn, uint8_t err) {\n    is_connected = (err == 0);\n    if (is_connected && recovery_in_progress) {\n        k_work_cancel_delayable(&recovery_guard_timeout);\n        recovery_in_progress = false;\n        LOG_WRN(\"P3 recovery v3: split connection recovered\");\n    }",
)
replace_once(
    peripheral,
    "static void recycled(void) {\n    if (enabled) {\n        low_duty_advertising = false;\n        k_work_submit(&advertising_work);\n    }\n}",
    "static void recycled(void) {\n    if (recovery_in_progress) {\n        LOG_WRN(\"P3 recovery v3: connection recycled; keeping recovery guard active\");\n    }\n\n    if (enabled) {\n        low_duty_advertising = false;\n        k_work_submit(&advertising_work);\n    }\n}",
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

print("P3 recovery candidate v3 source edits applied")
PY

git -C "$ROOT/zmk" diff --check

west build \
  -s zmk/app \
  -b 'nice_nano@2' \
  --pristine \
  -d "$ROOT/build/p3-peripheral-${SIDE}-recovery-v3" \
  -S zmk-usb-logging \
  -- \
  "-DBOARD_ROOT=$ROOT" \
  "-DZMK_CONFIG=$ROOT/config" \
  "-DCMAKE_PREFIX_PATH=$ROOT/zephyr/share/zephyr-package" \
  "-DSHIELD=$SHIELD" \
  "-DEXTRA_CONF_FILE=$ROOT/config/p3-peripheral-recovery-debug.conf"

echo "PASS: P3 peripheral ${SIDE} recovery candidate v3 built"
echo "UF2: $ROOT/build/p3-peripheral-${SIDE}-recovery-v3/zephyr/zmk.uf2"
