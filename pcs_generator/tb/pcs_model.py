from typing import Any

from pcs_generator.tb.pcs_sequence_item import PCSSequenceItem
from tb_utils.generic_model import GenericModel as BaseGenericModel


class GenericModel(BaseGenericModel):
    def __init__(self):
        super().__init__()
        self._current_frame = bytearray()
        self._in_frame = False
        self._frame_index = 0

    @staticmethod
    def _logic_to_int(value: Any) -> int:
        if isinstance(value, int):
            return value

        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"Could not convert {type(value).__name__} to an integer value"
            ) from exc

    @classmethod
    def _num_valid_bytes_from_tkeep(cls, tkeep: Any) -> int:
        tkeep_int = cls._logic_to_int(tkeep)
        max_tkeep = (1 << PCSSequenceItem.TKEEP_W) - 1

        if not 0 <= tkeep_int <= max_tkeep:
            raise ValueError(
                f"tkeep must be between 0 and 0x{max_tkeep:02X}, got 0x{tkeep_int:X}"
            )

        if tkeep_int != 0 and (tkeep_int & (tkeep_int + 1)) != 0:
            raise ValueError(
                f"tkeep must be contiguous LSB ones, got 0b{tkeep_int:0{PCSSequenceItem.TKEEP_W}b}"
            )

        return tkeep_int.bit_count()

    @classmethod
    def _extract_valid_bytes(cls, tdata: Any, num_valid_bytes: int) -> bytes:
        if not 0 <= num_valid_bytes <= PCSSequenceItem.TKEEP_W:
            raise ValueError(
                f"num_valid_bytes must be between 0 and {PCSSequenceItem.TKEEP_W}, "
                f"got {num_valid_bytes}"
            )

        tdata_int = cls._logic_to_int(tdata)
        return bytes((tdata_int >> (8 * byte_index)) & 0xFF for byte_index in range(num_valid_bytes))

    def assert_complete(self) -> None:
        if self._current_frame:
            raise RuntimeError(
                f"Frame {self._frame_index} incomplete: buffered {len(self._current_frame)} bytes"
            )

    async def process_notification(self, notification):
        if not isinstance(notification, PCSSequenceItem):
            raise TypeError(
                f"PCS model expects PCSSequenceItem notifications, got "
                f"{type(notification).__name__}"
            )

        contributes_payload = (not bool(notification.idle)) and bool(notification.tvalid)
        if not contributes_payload:
            return

        num_valid_bytes = self._num_valid_bytes_from_tkeep(notification.tkeep)
        if num_valid_bytes == 0:
            raise ValueError("Valid AXI beats must contain at least one valid byte")

        if not self._in_frame:
            self._in_frame = True

        self._current_frame.extend(self._extract_valid_bytes(notification.tdata, num_valid_bytes))

        if bool(notification.tlast):
            await self.expected_queue.put(bytes(self._current_frame))
            self._current_frame.clear()
            self._in_frame = False
            self._frame_index += 1
