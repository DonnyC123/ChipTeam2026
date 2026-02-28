from __future__ import annotations

from tb_utils.generic_model import GenericModel

from dataclasses import dataclass
from typing import Any, Dict, Literal

class AlignmentFinderBadInputModel(GenericModel):
    def __init__(self, data_width: int = 66, **_):
        super().__init__()
        self.data_width = int(data_width)
        self._reset()

    def _reset(self) -> None:
        self.locked = 0
        # pipeline regs for outputs
        self.bitslip_q = 0
        self.locked_q = 0

    def _hdr_from_word(self, word: int) -> int:
        shift = self.data_width - 2
        return (int(word) >> shift) & 0b11

    async def process_notification(self, notification: Dict[str, Any]):
        ev = notification.get("event")

        if ev == "reset":
            self._reset()
            return

        if ev != "cycle":
            return

        await self.expected_queue.put((self.locked_q, self.bitslip_q))

        data_valid = int(notification.get("data_valid", 0)) & 1
        word = int(notification.get("data", 0))
        hdr = self._hdr_from_word(word)

        hdr_valid = hdr in (0b01, 0b10)

        bitslip_next = 1 if (data_valid and not hdr_valid) else 0
        locked_next = 0  

        self.bitslip_q = bitslip_next
        self.locked_q = locked_next