from typing import Any, Dict

from tb_utils.generic_model import GenericModel


class RxModel(GenericModel):
    async def process_notification(self, notification: Dict[str, Any]):
        frame = notification.get("frame")
        if frame is None:
            return
        await self.expected_queue.put({"bytes": list(frame)})
