#!/usr/bin/env python3
import struct

MAGIC = 0xAE
MAJOR = 1
MINOR = 0
SIZE = 32
HEADER = 8
MAX_PAYLOAD = 24

HELLO = 0x01
GET_STATE = 0x02
SET_LAYER_INTENT = 0x10
STATE_SNAPSHOT = 0x80
HELLO_ACK = 0x81
ACK = 0x90
NACK = 0x91


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
    return buf[3], struct.unpack_from("<H", buf, 6)[0], buf[8:8+n]


def main():
    vectors = [
        (HELLO, 1, struct.pack("<I", 0x12345678)),
        (GET_STATE, 2, b""),
        (SET_LAYER_INTENT, 3, bytes([8, 0])),
        (SET_LAYER_INTENT, 4, bytes([10, 1])),
        (ACK, 4, bytes([SET_LAYER_INTENT])),
        (NACK, 5, bytes([SET_LAYER_INTENT, 4])),
    ]

    for expected_type, expected_seq, expected_payload in vectors:
        v = frame(expected_type, expected_seq, expected_payload)
        msg_type, seq, payload = parse(v)
        assert msg_type == expected_type
        assert seq == expected_seq
        assert payload == expected_payload
        assert len(v) == SIZE
        assert all(x == 0 for x in v[HEADER + len(payload):])

    bitmap = bytearray(16)
    for ref in (0, 3, 8, 10):
        bitmap[ref // 8] |= 1 << (ref % 8)
    snapshot = struct.pack("<HBBBB", 7, 1, 1, 10, 8) + bytes([16]) + bytes(bitmap) + b"\x00"
    assert len(snapshot) == 24
    snap_frame = frame(STATE_SNAPSHOT, 6, snapshot)
    t, seq, p = parse(snap_frame)
    assert t == STATE_SNAPSHOT and seq == 6 and len(p) == 24
    assert p[6] == 16
    assert p[7 + (10 // 8)] & (1 << (10 % 8))

    hello_ack = struct.pack("<IHHHI", 0x12345678, 1, 0x0003, 1, 0x53454C31)
    assert len(hello_ack) == 14
    assert len(frame(HELLO_ACK, 1, hello_ack)) == 32

    print("PASS: HID wire v1 vectors (8/8)")


if __name__ == "__main__":
    main()
