from typing import Any, Dict, Tuple

from rx_fifo.tb.rx_fifo_sequence_item import RXFifoSequenceItem
from tb_utils.generic_model import GenericModel


def _mask_from_bytes_valid(mask: int) -> Tuple[bool, ...]:
    # Mask bit i controls byte i of the input beat (byte 0 = LSB byte).
    return tuple(bool((mask >> idx) & 1) for idx in range(8))


class RXFifoModel(GenericModel):
    DATA_IN_W = RXFifoSequenceItem.DATA_IN_W
    IN_MASK_W = RXFifoSequenceItem.IN_MASK_W
    DATA_OUT_W = RXFifoSequenceItem.DATA_OUT_W
    OUT_BYTES = DATA_OUT_W // 8

    def __init__(self):
        super().__init__()
        # Kept input bytes are accumulated until send_i commits one output row.
        self._pending_bytes: list[int] = []
        self._last_input_mask = 0

    @staticmethod
    def _bytes_from_data(data: int) -> Tuple[int, ...]:
        # LSB byte first, matching the DUT's bit-ordered packing into the
        # 256-bit output buffer (byte 0 of beat 0 lands at output bits [7:0]).
        return tuple((data >> (idx * 8)) & 0xFF for idx in range(8))

    def _clear_pending(self):
        self._pending_bytes.clear()
        self._last_input_mask = 0

    def _append_masked_data(self, data: int, mask: int):
        self._last_input_mask = mask & ((1 << self.IN_MASK_W) - 1)
        for byte, keep_byte in zip(
            self._bytes_from_data(data),
            _mask_from_bytes_valid(self._last_input_mask),
        ):
            if keep_byte:
                self._pending_bytes.append(byte)

    def _packed_pending_data(self) -> int:
        if len(self._pending_bytes) > self.OUT_BYTES:
            raise ValueError(
                f"RX FIFO model only supports one {self.DATA_OUT_W}-bit output row, "
                f"got {len(self._pending_bytes)} bytes"
            )

        # First-appended byte lands at output bits [7:0]; subsequent bytes
        # stack upward, matching the DUT's bottom-up beat fill.
        packed_data = 0
        for idx, byte in enumerate(self._pending_bytes):
            packed_data |= byte << (idx * 8)
        return packed_data

    async def process_notification(self, notification: Dict[str, Any]):
        if notification.get("cancel"):
            self._clear_pending()
            return

        # Drop cancels all accumulated packet data before any commit.
        if notification["drop_i"]:
            self._clear_pending()
            return

        if notification["valid_i"]:
            self._append_masked_data(notification["data_i"], notification["mask_i"])

        # send_i commits the row in the DUT regardless of m_axi.ready;
        # backpressure only delays when the row drains out to the consumer.
        if notification["send_i"]:
            await self.expected_queue.put(
                {
                    "data": self._packed_pending_data(),
                    "last_mask": self._last_input_mask & 0xFF,
                    "last": True,
                }
            )
            self._clear_pending()
