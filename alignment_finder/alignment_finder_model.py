from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
from tb_utils.generic_model import GenericModel

MASK66 = (1 << 66) - 1

def get_hdr_2b(word66):
    return (word66 >> 64) & 0b11

def hdr_is_valid(header):
    return header in (0b01, 0b10)

@dataclass
class AlignFinder66Core:
    lock_good_cnt: int = 32
    unlock_bad_cnt: int = 8

    offset: int = 0
    buf132: int = 0
    have_prev: bool = False

    locked: bool = False
    good_run: int = 0
    bad_run: int = 0

    def reset(self):
        self.offset = 0
        self.buf132 = 0
        self.have_prev = False
        self.locked = False
        self.good_run = 0
        self.bad_run = 0

    def step(self, din, vin) -> Tuple[int, bool, bool, bool]:
        if not vin:
            return 0, False, self.locked, False

        din &= MASK66

        if not self.have_prev:
            self.buf132 = din
            self.have_prev = True

            dout = din
            header_ok = hdr_is_valid(get_hdr_2b(dout))
            self.update_lock_state(header_ok)
            return dout, True, self.locked, False

        prev66 = self.buf132 & MASK66
        self.buf132 = (prev66 << 66) | din

        dout = self.slice_word()
        header_ok = hdr_is_valid(get_hdr_2b(dout))

        bitslip = False
        if not self.locked and not header_ok:
            self.offset = (self.offset + 1) % 66
            bitslip = True

            dout_66 = self.slice_word()
            header_ok = hdr_is_valid(get_hdr_2b(dout_66))

        self.update_lock_state(header_ok)
        return dout, True, self.locked, bitslip

    def slice_word(self) -> int:
        shift = 66 - self.offset
        return (self.buf132 >> shift) & MASK66

    def update_lock_state(self, header_ok):
        if not self.locked:
            if header_ok:
                self.good_run += 1
            else:
                self.good_run = 0

            if self.good_run >= self.lock_good_cnt:
                self.locked = True
                self.bad_run = 0
        else:
            if header_ok:
                self.bad_run = 0
            else:
                self.bad_run += 1

            if self.bad_run >= self.unlock_bad_cnt:
                self.locked = False
                self.good_run = 0


AlignOut = Tuple[int, bool, bool, bool]

class AlignFinderModel(GenericModel):
    def __init__(
        self,
        *,
        lock_good_cnt: int = 32,
        unlock_bad_cnt: int = 8,
    ):
        super().__init__()
        self.core = AlignFinder66Core(
            lock_good_cnt=lock_good_cnt,
            unlock_bad_cnt=unlock_bad_cnt,
        )

    async def _enqueue_expected(self, out):
        await self.expected_queue.put(out)

    async def process_notification(self, notification):
        ev = notification.get("event")

        if ev in ("start", "reset"):
            self.core.reset()
            return

        if ev in ("input", "cycle", "sample"):
            din_66: Optional[int] = (
                notification.get("din_66")
                if notification.get("din_66") is not None
                else notification.get("din")
            )
            vin = bool(
                notification.get("valid")
                if notification.get("valid") is not None
                else notification.get("vin", False)
            )

            dout_66, vout, locked, bitslip = self.core.step(int(din_66), vin)
            await self._enqueue_expected((dout_66, vout, locked, bitslip))
            return
        return
