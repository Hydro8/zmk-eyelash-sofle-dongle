# Æklipse — PHYSICAL_KEY_STATE epoch recovery fix

## Order

`AEKLIPSE-00-01-20260903-007`

## Baselines

- firmware parent: `b42511038a6d6ea2cd0a0fad3366311a047f6ad1`
- dongle-display parent: `a287cb265f409f4b11903b848f71c16815f48fc0`
- firmware work branch: `aeklipse/physical-key-state-epoch-fix-p2`
- module work branch: `aeklipse/physical-key-state-epoch-fix-p2`
- corrected module commit: `d136104c42e19830757831ca45ac3d4cab730f7b`
- pinned ZMK source remains `641514a97db345f499dd50b0360e594270f008fe`

## Root cause

The previous implementation made `physical_epoch_tainted=true` whenever the split link was not `ALL_CONNECTED`, but no code path cleared that taint. After startup or any BLE link transition, every `PHYSICAL_KEY_STATE` frame therefore remained `valid=0` forever.

## Recovery boundary

The corrected state machine preserves fail-closed semantics:

1. any state other than `ALL_CONNECTED` invalidates the physical state, clears the bitmap and taints the epoch;
2. the first observation of `ALL_CONNECTED` clears the permanent taint but does **not** make the physical state valid; it opens a new empty epoch waiting for an observable ZMK position event;
3. repeated `ALL_CONNECTED` polls cannot bypass this observation gate;
4. the first in-domain `zmk_position_state_changed` event while the link is `ALL_CONNECTED` establishes the new observable epoch, then its press/release transition is applied to the zeroed bitmap;
5. an out-of-domain position or a new link loss invalidates the epoch again.

This intentionally never reconstructs a key as pressed merely because it was pressed before a BLE loss.

## Why the event boundary is grounded in pinned ZMK

Pinned ZMK `641514a9` clears each split peripheral central-side `position_state` when the peripheral slot is released. After reconnect, the BLE position notification carries the peripheral's current position bitmap and the central emits `zmk_position_state_changed` events for changed bits. The Æklipse module therefore waits for actual post-reconnect position evidence instead of treating `ALL_CONNECTED` alone as proof of a complete physical bitmap.

## Wire contract

Unchanged:

- report size: 32 bytes
- type: `0x83`
- capability: bit 3
- payload length: 10 bytes
- `position_count=64`
- 8-byte LSB-first bitmap
- invalid state serializes `valid=0` and a zero bitmap
- no valid physical publication before HID v1 negotiation

## Deterministic host tests

New `scripts/test-physical-epoch.py` covers:

- startup disconnected -> `ALL_CONNECTED`;
- observation gate after recovery;
- `ALL_CONNECTED` -> loss -> `ALL_CONNECTED`;
- stale pressed state clearing;
- release/press event after reconnect;
- out-of-domain invalidation;
- repeated `ALL_CONNECTED` polls not bypassing the gate.

Existing `scripts/test-hid-wire-v1.py` remains the wire/vector regression gate and must also pass.

## Qualification still required

Before RESULT PASS:

1. run `scripts/test-hid-wire-v1.py`;
2. run `scripts/test-physical-epoch.py`;
3. build all four Selenium targets locally outside GitHub Actions.

Physical requalification remains owned by Agent 04 after this host/build gate.
