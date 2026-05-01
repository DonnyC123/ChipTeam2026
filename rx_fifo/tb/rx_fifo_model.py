from collections import deque
from typing import Any, Deque, Dict, List, Tuple

from rx_fifo.tb.rx_fifo_sequence_item import RXFifoSequenceItem
from tb_utils.generic_model import GenericModel


class RXFifoModel(GenericModel):
    DATA_IN_W = RXFifoSequenceItem.DATA_IN_W
    IN_MASK_W = RXFifoSequenceItem.IN_MASK_W

    STATUS_VALID = "valid"
    STATUS_DROPPED = "dropped"

    def __init__(self):
        super().__init__()
        self._pending_beats: List[Tuple[int, int]] = []
        # Packets that have been enqueued but whose DUT outcome (commit vs.
        # revert) is not yet confirmed. Same dict objects are referenced from
        # `expected_queue`, so flipping `status` here updates the queued entry
        # in place.
        self._tentative_packets: Deque[Dict[str, Any]] = deque()

    def _clear_pending(self):
        self._pending_beats.clear()

    async def process_notification(self, notification: Dict[str, Any]):
        if notification.get("cancel"):
            # cancel_o pulses for two reasons:
            #   (a) drop_i was asserted - in that case the model already
            #       cleared `_pending_beats` synchronously when the drop_i
            #       notification arrived, and never enqueued a tentative
            #       packet, so there is nothing to pop here.
            #   (b) fifo_full collided with send_i - the DUT reverted the
            #       commit, so the front-most tentative packet (the next one
            #       the driver was about to push through the DUT) is dropped.
            # We can't tell (a) from (b) at the model level, so we only pop
            # when there is a tentative packet awaiting confirmation. drop_i
            # arrives before the resulting cancel notification and clears
            # `_pending_beats`, so its cancel will simply find no tentative
            # packet to pop.
            if self._tentative_packets:
                pkt = self._tentative_packets.popleft()
                pkt["status"] = self.STATUS_DROPPED
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
            packet: Dict[str, Any] = {
                "beats": [beat_data for beat_data, _ in self._pending_beats],
                "status": self.STATUS_VALID,
            }
            self._tentative_packets.append(packet)
            await self.expected_queue.put(packet)
            self._clear_pending()
