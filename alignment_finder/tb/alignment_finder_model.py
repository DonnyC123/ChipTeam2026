from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal

from tb_utils.generic_model import GenericModel

State = Literal["SEARCH", "LOCKED"]

@dataclass
class StreamAlignCfg:
    block_len: int = 66
    lock_good_cnt: int = 32
    unlock_bad_cnt: int = 8
    valid_headers: tuple[int, int] = (0b01, 0b10)


class AlignmentFinderModel(GenericModel):
    def __init__(self, data_width: int = 66, good_count: int = 32, bad_count: int = 8, **_):
        super().__init__()
        self.data_width = int(data_width)
        self.cfg = StreamAlignCfg(
            block_len=self.data_width,
            lock_good_cnt=int(good_count),
            unlock_bad_cnt=int(bad_count),
        )
        self._reset()

    def _reset(self) -> None:
        self.state: State = "SEARCH"
        self.good_count: int = 0
        self.bad_count: int = 0

        self.locked: int = 0
        self.bitslip: int = 0

    def _hdr_from_word(self, word: int) -> int:
        shift = self.cfg.block_len - 2
        return (int(word) >> shift) & 0b11

    def _hdr_valid(self, hdr: int) -> bool:
        return hdr in self.cfg.valid_headers

    async def _emit(self, *, bitslip: int, locked_val: int) -> None:
        await self.expected_queue.put((locked_val, bitslip))

    async def process_notification(self, notification: Dict[str, Any]):
        ev = notification.get("event")

        if ev == "reset":
            self._reset()
            return

        if ev != "cycle":
            return

        data_valid = int(notification.get("data_valid", 0)) & 1
        word = int(notification.get("data", 0))
        hdr = self._hdr_from_word(word)
        hdr_ok = self._hdr_valid(hdr)

        next_state = self.state
        next_good = self.good_count
        next_bad = self.bad_count

        bitslip_next = 0

        if self.state == "SEARCH":
            if data_valid:
                if hdr_ok:
                    if next_good >= self.cfg.lock_good_cnt - 1:
                        next_state = "LOCKED"
                        next_good = 0
                    else:
                        next_good += 1
                else:
                    bitslip_next = 1
                    next_good = 0
            next_bad = 0

        elif self.state == "LOCKED":
            if data_valid:
                if hdr_ok:
                    next_bad = 0
                else:
                    if next_bad >= self.cfg.unlock_bad_cnt - 1:
                        next_state = "SEARCH"
                        next_bad = 0
                        next_good = 0
                    else:
                        next_bad += 1

        locked_next = 1 if next_state == "LOCKED" else 0

        await self._emit(bitslip=self.bitslip, locked_val=self.locked)

        self.state = next_state
        self.good_count = next_good
        self.bad_count = next_bad
        self.locked = locked_next
        self.bitslip = bitslip_next