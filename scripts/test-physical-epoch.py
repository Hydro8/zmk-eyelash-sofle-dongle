#!/usr/bin/env python3

LINK_DISCONNECTED = 0
LINK_SOME_CONNECTED = 1
LINK_ALL_CONNECTED = 2
POSITION_COUNT = 64


class PhysicalEpoch:
    def __init__(self):
        self.valid = False
        self.tainted = True
        self.waiting = False
        self.bitmap = 0

    def invalidate(self):
        self.valid = False
        self.tainted = True
        self.waiting = False
        self.bitmap = 0

    def refresh(self, link_state):
        if link_state != LINK_ALL_CONNECTED:
            self.invalidate()
            return
        if self.tainted:
            self.tainted = False
            self.waiting = True
            self.valid = False
            self.bitmap = 0

    def position(self, link_state, position, pressed):
        self.refresh(link_state)
        if not 0 <= position < POSITION_COUNT:
            self.invalidate()
            return
        if link_state != LINK_ALL_CONNECTED:
            self.invalidate()
            return
        if self.waiting:
            self.waiting = False
            self.valid = True
        if not self.valid:
            return
        mask = 1 << position
        if pressed:
            self.bitmap |= mask
        else:
            self.bitmap &= ~mask

    def pressed(self):
        return {i for i in range(POSITION_COUNT) if self.bitmap & (1 << i)}


def main():
    # 1. Startup disconnected -> ALL_CONNECTED stays fail-closed until an observable position event.
    e = PhysicalEpoch()
    e.refresh(LINK_DISCONNECTED)
    assert not e.valid and e.tainted and e.pressed() == set()
    e.refresh(LINK_ALL_CONNECTED)
    assert not e.valid and not e.tainted and e.waiting and e.pressed() == set()

    # 2. First current position event establishes the new observable epoch.
    e.position(LINK_ALL_CONNECTED, 5, True)
    assert e.valid and not e.waiting and e.pressed() == {5}

    # 3. ALL_CONNECTED -> loss clears stale pressed state and taints the epoch.
    e.refresh(LINK_SOME_CONNECTED)
    assert not e.valid and e.tainted and e.pressed() == set()

    # 4. Recovery opens a fresh empty epoch; a key held before loss is never reconstructed by assumption.
    e.refresh(LINK_ALL_CONNECTED)
    assert not e.valid and e.waiting and e.pressed() == set()

    # 5. A release/press actually observed after reconnect can establish/update current state.
    e.position(LINK_ALL_CONNECTED, 5, False)
    assert e.valid and e.pressed() == set()
    e.position(LINK_ALL_CONNECTED, 32, True)
    assert e.valid and e.pressed() == {32}

    # 6. Out-of-domain event invalidates the epoch fail-closed.
    e.position(LINK_ALL_CONNECTED, 64, True)
    assert not e.valid and e.tainted and e.pressed() == set()

    # 7. Repeated ALL_CONNECTED polls do not bypass the observation gate.
    e.refresh(LINK_ALL_CONNECTED)
    assert not e.valid and e.waiting
    e.refresh(LINK_ALL_CONNECTED)
    assert not e.valid and e.waiting

    print("PASS: physical epoch recovery vectors (7/7)")


if __name__ == "__main__":
    main()
