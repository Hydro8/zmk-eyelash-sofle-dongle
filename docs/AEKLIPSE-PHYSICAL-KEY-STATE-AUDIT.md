# Æklipse — Selenium PHYSICAL_KEY_STATE audit

## Baseline

- firmware parent: `aeklipse/hid-wire-v1-p1@9d4092e753f35e364dcd94eb859561af526b942b`
- work branch: `aeklipse/physical-key-state-p2`
- ZMK pin: `641514a97db345f499dd50b0360e594270f008fe`
- active shield tree: `boards/shields/eyelash_sofle`
- historical duplicate `boards/shields/eyeslash_solfe` was compared for the transform: its 64-entry transform is identical; it is not used by the qualified build targets and is not removed in this change.

## Proven position identity

`position_id` is **not** a keycode and is **not** an arbitrary Æklipse numbering. It is the `zmk_position_state_changed.position` value produced after the active ZMK matrix transform.

The proof chain on the pinned sources is:

1. each physical peripheral scans local row/column coordinates;
2. the active `default_transform` maps row/column into a flattened logical position;
3. the right peripheral applies `col-offset = <7>` before the transform, so right local columns occupy the right-side global matrix columns;
4. ZMK raises `zmk_position_state_changed` with that transformed `position`;
5. the split peripheral transports the position event unchanged and the central recreates `zmk_position_state_changed` with the transported `position`;
6. therefore the dongle central sees the same logical position used by the ZMK keymap.

This identity is stable for a given Selenium physical layout/transform and independent of the binding on any layer.

## Cardinality and exact order

The active transform has 64 entries, so:

- `position_count = 64`
- valid `position_id` range = `0..63`
- bitmap size = `ceil(64/8) = 8` bytes
- bit `n` represents `position_id == n`, least-significant bit first inside each byte.

Flattened transform rows:

| Logical row | position_id range | left global columns | right global columns |
|---|---:|---|---|
| 0 | 0..12 | 0..5 → positions 0..5 | 7..13 → positions 6..12 |
| 1 | 13..25 | 0..5 → positions 13..18 | 7..13 → positions 19..25 |
| 2 | 26..38 | 0..5 → positions 26..31 | 7..13 → positions 32..38 |
| 3 | 39..51 | 0..5 → positions 39..44 | 7..13 → positions 45..51 |
| 4 | 52..63 | 0..5 → positions 52..57 | 7..12 → positions 58..63 |

The keymap geometry has the same 13/13/13/13/12 binding cardinality, confirming that transformed position order and keymap binding order share the same 64-position domain.

## Wire extension

The existing 32-byte HID v1 framing is unchanged.

Additive P2 extension:

- capability: `AEK_CAP_PHYSICAL_KEY_STATE = bit 3`
- event type: `PHYSICAL_KEY_STATE = 0x83`
- payload length: 10 bytes
- payload byte 0: `valid` (`0` or `1`)
- payload byte 1: `position_count` (`64`)
- payload bytes 2..9: 8-byte pressed-position bitmap.

Rules:

- multiple simultaneous positions are represented by multiple set bits;
- packets use sequence `0` when unsolicited;
- HELLO/GET_STATE may return the current physical state after negotiation;
- before a valid v1 session, no physical packet is published to the host;
- if split state is not `ALL_CONNECTED`, physical state is invalidated and serialized with `valid=0` and a zero bitmap;
- any transformed position outside `0..63` invalidates the physical epoch instead of being truncated or renumbered;
- after a split-link uncertainty the implementation stays fail-closed instead of claiming a reconstructed bitmap without proof;
- USB session loss alone does not fabricate or remap position identity.

## Test vectors

Host vectors cover:

- zero pressed positions;
- one pressed position;
- multiple simultaneous positions crossing left/right domains;
- maximum position 63;
- invalid state with zero bitmap;
- session non-negotiated gate;
- existing v1 malformed-padding rejection.

## Remaining UNKNOWN / later physical qualification

Not claimed by this firmware-only gate:

- whether BLE reconnection delivers enough state to recover a valid bitmap without reboot after a link-loss epoch;
- physical Mac ↔ dongle observation of position 0..63;
- latency/coalescing requirements for overlay rendering;
- behavior while a key remains physically held across a peripheral BLE loss.

Those cases require the later physical/E2E gate and must not be inferred from compilation alone.
