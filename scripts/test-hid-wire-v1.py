#!/usr/bin/env python3
import struct

MAGIC = 0xAE
MAJOR = 1
MINOR = 0
SIZE = 32
HEADER = 8
MAX_PAYLOAD = 24
NONE_REF = 0xFF

HELLO = 0x01
GET_STATE = 0x02
SET_LAYER_INTENT = 0x10
STATE_SNAPSHOT = 0x80
HELLO_ACK = 0x81
LINK_STATE_CHANGED = 0x82
ACK = 0x90
NACK = 0x91

UNSUPPORTED_VERSION = 0x01
UNSUPPORTED_MESSAGE = 0x02
INVALID_PAYLOAD = 0x03
INVALID_LAYER = 0x04
NOT_READY = 0x05
KEYBOARD_UNAVAILABLE = 0x06
BUSY = 0x07
INTERNAL_ERROR = 0x08

LINK_DISCONNECTED = 0
LINK_SOME_CONNECTED = 1
LINK_ALL_CONNECTED = 2


def frame(msg_type, seq, payload=b"", flags=0):
    assert len(payload) <= MAX_PAYLOAD
    out = bytearray(SIZE)
    out[:8] = bytes([MAGIC, MAJOR, MINOR, msg_type, flags, len(payload)]) + struct.pack("<H", seq)
    out[HEADER:HEADER + len(payload)] = payload
    return bytes(out)


def parse(buf):
    assert len(buf) == SIZE
    assert buf[0] == MAGIC
    assert buf[1] == MAJOR
    assert buf[2] <= MINOR
    assert buf[4] == 0
    n = buf[5]
    assert n <= MAX_PAYLOAD
    assert all(x == 0 for x in buf[HEADER + n:])
    return buf[3], struct.unpack_from("<H", buf, 6)[0], buf[8:8+n]


def snapshot_payload(revision, valid, link_state, highest_ref, smart_ref, active_refs):
    assert link_state in {LINK_DISCONNECTED, LINK_SOME_CONNECTED, LINK_ALL_CONNECTED}
    if not valid:
        assert highest_ref == NONE_REF
        assert smart_ref == NONE_REF
        assert not active_refs
    elif highest_ref != NONE_REF:
        assert highest_ref in active_refs

    bitmap = bytearray(16)
    for ref in active_refs:
        assert 0 <= ref <= 127
        bitmap[ref // 8] |= 1 << (ref % 8)
    payload = struct.pack("<HBBBB", revision, int(valid), link_state, highest_ref, smart_ref)
    payload += bytes([16]) + bytes(bitmap) + b"\x00"
    assert len(payload) == 24
    return payload


def main():
    vectors = [
        (HELLO, 1, struct.pack("<I", 0x12345678)),
        (GET_STATE, 2, b""),
        (SET_LAYER_INTENT, 3, bytes([8, 0])),
        (SET_LAYER_INTENT, 4, bytes([10, 1])),
        (ACK, 4, bytes([SET_LAYER_INTENT])),
        (NACK, 5, bytes([SET_LAYER_INTENT, INVALID_LAYER])),
    ]

    for expected_type, expected_seq, expected_payload in vectors:
        msg_type, seq, payload = parse(frame(expected_type, expected_seq, expected_payload))
        assert msg_type == expected_type
        assert seq == expected_seq
        assert payload == expected_payload

    valid_snapshot = snapshot_payload(7, True, LINK_ALL_CONNECTED, 10, 8, [0, 3, 8, 10])
    t, seq, p = parse(frame(STATE_SNAPSHOT, 6, valid_snapshot))
    assert t == STATE_SNAPSHOT and seq == 6 and len(p) == 24
    assert p[6] == 16
    assert p[7 + (10 // 8)] & (1 << (10 % 8))

    invalid_snapshot = snapshot_payload(8, False, LINK_SOME_CONNECTED, NONE_REF, NONE_REF, [])
    _, _, invalid = parse(frame(STATE_SNAPSHOT, 0, invalid_snapshot))
    assert invalid[2] == 0
    assert invalid[4] == NONE_REF and invalid[5] == NONE_REF
    assert not any(invalid[7:23])

    link = bytes([LINK_DISCONNECTED, 0])
    assert parse(frame(LINK_STATE_CHANGED, 0, link))[2] == link

    hello_ack = struct.pack("<IHHHI", 0x12345678, 1, 0x0003, 1, 0x53454C31)
    assert len(hello_ack) == 14
    assert len(frame(HELLO_ACK, 1, hello_ack)) == 32

    assert [UNSUPPORTED_VERSION, UNSUPPORTED_MESSAGE, INVALID_PAYLOAD, INVALID_LAYER,
            NOT_READY, KEYBOARD_UNAVAILABLE, BUSY, INTERNAL_ERROR] == list(range(1, 9))

    malformed = bytearray(frame(GET_STATE, 9))
    malformed[31] = 1
    rejected = False
    try:
        parse(bytes(malformed))
    except AssertionError:
        rejected = True
    assert rejected, "non-zero unused payload byte must fail"

    print("PASS: HID wire v1 vectors (12/12)")


if __name__ == "__main__":
    main()
