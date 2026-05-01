from typing import Any, Dict, List, Tuple

from rx_fifo.tb.rx_fifo_sequence_item import RXFifoSequenceItem
from tb_utils.generic_model import GenericModel


class RXFifoModel(GenericModel):
    DATA_IN_W = RXFifoSequenceItem.DATA_IN_W
    IN_MASK_W = RXFifoSequenceItem.IN_MASK_W

    def __init__(self):
        super().__init__()
        # (data, mask) per accepted input beat in the current packet.
        self._pending_beats: List[Tuple[int, int]] = []

    def _clear_pending(self):
        self._pending_beats.clear()

    async def process_notification(self, notification: Dict[str, Any]):
        if notification.get("cancel"):
            self._clear_pending()
            return

        if notification["drop_i"]:
            self._clear_pending()
            return

        if not notification["valid_i"]:
            return

        data = notification["data_i"] & ((1 << self.DATA_IN_W) - 1)
        mask = notification["mask_i"] & ((1 << self.IN_MASK_W) - 1)
        self._pending_beats.append((data, mask))

        if notification["send_i"]:
            last_idx = len(self._pending_beats) - 1
            for idx, (beat_data, _) in enumerate(self._pending_beats):
                await self.expected_queue.put(
                    {
                        "data": beat_data,
                        "last": idx == last_idx,
                    }
                )
            self._clear_pending()
