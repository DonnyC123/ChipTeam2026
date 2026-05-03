from typing import Any, Dict

from tb_utils.generic_model import GenericModel


class RxModel(GenericModel):
    """Expected-packet model for rx_tb.

    Fed by `RxSequence` via `notify_subscribers({"frame": [...]})` whenever the
    sequence sends an Ethernet frame. Each notification queues one expected
    packet as `{"bytes": [...]}`, matching the format produced by
    `RxEventMonitor`."""

    async def process_notification(self, notification: Dict[str, Any]):
        frame = notification.get("frame")
        if frame is None:
            return
        await self.expected_queue.put({"bytes": list(frame)})
