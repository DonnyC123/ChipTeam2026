from typing import Any, Dict

from tb_utils.generic_model import GenericModel


class EthernetParserModel(GenericModel):
    IDLE = "IDLE"
    PAUSE = "PAUSE"
    PARSE_L0 = "PARSE_L0"
    PARSE_L4 = "PARSE_L4"

    SOF0_MASK = 0xFE
    SOF4_MASK = 0xE0
    OUTPUT_OTHER = 2

    def __init__(self):
        super().__init__()
        self.state = self.IDLE

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        if value is None:
            return default
        return int(value)

    @staticmethod
    def _to_bool(value: Any) -> bool:
        return bool(value)

    async def process_notification(self, notification: Dict[str, Any]):
        data_valid = self._to_bool(notification.get("data_valid", False))
        bytes_valid = self._to_int(notification.get("bytes_valid"), 0)
        expected_output = self._to_int(
            notification.get("expected_outputs_o"), self.OUTPUT_OTHER
        )

        if self.state == self.IDLE:
            if data_valid and bytes_valid == self.SOF0_MASK:
                self.state = self.PAUSE
            elif data_valid and bytes_valid == self.SOF4_MASK:
                self.state = self.PARSE_L4
            return

        if self.state == self.PAUSE:
            if data_valid:
                self.state = self.PARSE_L0
            return

        if self.state in (self.PARSE_L0, self.PARSE_L4):
            if data_valid:
                await self.expected_queue.put({"outputs_o": expected_output})
                self.state = self.IDLE
