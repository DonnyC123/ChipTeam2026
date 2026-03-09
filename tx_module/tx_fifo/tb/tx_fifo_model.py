from collections import deque

from tb_utils.generic_model import GenericModel


class TxFifoModel(GenericModel):
    """Reference model for TX FIFO width conversion with occupancy tracking."""

    BEATS_PER_WORD = 4
    PCS_DATA_W = 64
    PCS_VALID_W = 8

    def __init__(self, depth: int = 64):
        super().__init__()
        self.depth = depth
        self.entries = deque()
        self.beat_idx = 0

    async def process_notification(self, notification):
        op = notification.get("op")

        if op == "write":
            data_256 = notification["data"]
            valid_32 = notification["valid"]
            if len(self.entries) < self.depth:
                self.entries.append((data_256, valid_32))

        elif op == "read":
            if not self.entries:
                return

            data_256, valid_32 = self.entries[0]
            mask_64 = (1 << self.PCS_DATA_W) - 1
            mask_8 = (1 << self.PCS_VALID_W) - 1

            pcs_data = (data_256 >> (self.beat_idx * self.PCS_DATA_W)) & mask_64
            pcs_valid = (valid_32 >> (self.beat_idx * self.PCS_VALID_W)) & mask_8
            await self.expected_queue.put((pcs_data, pcs_valid))

            self.beat_idx += 1
            if self.beat_idx == self.BEATS_PER_WORD:
                self.beat_idx = 0
                self.entries.popleft()