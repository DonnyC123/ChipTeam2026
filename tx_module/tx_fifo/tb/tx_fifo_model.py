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

        if op == "cycle":
            write_en = bool(notification.get("write_en", False))
            read_en = bool(notification.get("read_en", False))
            data_256 = int(notification.get("data", 0))
            valid_32 = int(notification.get("valid", 0))
            last_word = int(notification.get("last", 0))

            empty = len(self.entries) == 0
            full = len(self.entries) >= self.depth

            do_write = write_en and (not full)
            do_read = read_en and (not empty)

            if do_read:
                rd_data_256, rd_valid_32, rd_last = self.entries[0]
                mask_64 = (1 << self.PCS_DATA_W) - 1
                mask_8 = (1 << self.PCS_VALID_W) - 1

                pcs_data = (rd_data_256 >> (self.beat_idx * self.PCS_DATA_W)) & mask_64
                pcs_valid = (rd_valid_32 >> (self.beat_idx * self.PCS_VALID_W)) & mask_8
                pcs_last = 1 if (rd_last and self.beat_idx == (self.BEATS_PER_WORD - 1)) else 0
                await self.expected_queue.put((pcs_data, pcs_valid, pcs_last))

            if do_write:
                self.entries.append((data_256, valid_32, last_word))

            if do_read:
                self.beat_idx += 1
                if self.beat_idx == self.BEATS_PER_WORD:
                    self.beat_idx = 0
                    self.entries.popleft()
            return

        # Backward-compatible path for older sequences.
        if op == "write":
            data_256 = int(notification.get("data", 0))
            valid_32 = int(notification.get("valid", 0))
            last_word = int(notification.get("last", 0))
            if len(self.entries) < self.depth:
                self.entries.append((data_256, valid_32, last_word))
            return

        if op == "read":
            if not self.entries:
                return

            rd_data_256, rd_valid_32, rd_last = self.entries[0]
            mask_64 = (1 << self.PCS_DATA_W) - 1
            mask_8 = (1 << self.PCS_VALID_W) - 1

            pcs_data = (rd_data_256 >> (self.beat_idx * self.PCS_DATA_W)) & mask_64
            pcs_valid = (rd_valid_32 >> (self.beat_idx * self.PCS_VALID_W)) & mask_8
            pcs_last = 1 if (rd_last and self.beat_idx == (self.BEATS_PER_WORD - 1)) else 0
            await self.expected_queue.put((pcs_data, pcs_valid, pcs_last))

            self.beat_idx += 1
            if self.beat_idx == self.BEATS_PER_WORD:
                self.beat_idx = 0
                self.entries.popleft()
