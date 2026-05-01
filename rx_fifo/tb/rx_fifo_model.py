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
        # Cancel notifications are observed by RXFifoEventMonitor; the model
        # only cares about the input-side stimulus.
        if notification.get("cancel"):
            return

        if notification["drop_i"]:
            # Test deliberately aborted this packet via drop_i. Forward what
            # we have so the checker can account for it.
            if self._pending_beats:
                await self.expected_queue.put(
                    {
                        "beats": [beat_data for beat_data, _ in self._pending_beats],
                        "dropped": True,
                    }
                )
            self._clear_pending()
            return

        if not notification["valid_i"]:
            return

        data = notification["data_i"] & ((1 << self.DATA_IN_W) - 1)
        mask = notification["mask_i"] & ((1 << self.IN_MASK_W) - 1)
        self._pending_beats.append((data, mask))

        if notification["send_i"]:
            await self.expected_queue.put(
                {
                    "beats": [beat_data for beat_data, _ in self._pending_beats],
                    "dropped": False,
                }
            )
            self._clear_pending()
