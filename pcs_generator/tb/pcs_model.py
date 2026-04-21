from collections import deque
from typing import Any

from pcs_generator.tb.pcs_sequence_item import PCSSequenceItem
from pcs_generator.tb.pcs_debug import (
    AxiActivityRecord,
    ExpectedFrameRecord,
    TRACE_HISTORY_DEPTH,
    bounded_trace,
    current_time_ns,
)
from tb_utils.generic_model import GenericModel as BaseGenericModel


class GenericModel(BaseGenericModel):
    def __init__(self):
        super().__init__()
        self._current_frame = bytearray()
        self._current_frame_trace: list[AxiActivityRecord] = []
        self._current_payload_beats: list[AxiActivityRecord] = []
        self._in_frame = False
        self._frame_index = 0
        self._activity_index = 0
        self._recent_activity: deque[AxiActivityRecord] = deque(maxlen=TRACE_HISTORY_DEPTH)

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
            trace_dump = "\n".join(record.describe() for record in self._current_frame_trace)
            raise RuntimeError(
                f"Frame {self._frame_index} is incomplete: missing tlast for "
                f"{len(self._current_frame)} buffered bytes\n"
                f"Recent AXI activity:\n{trace_dump}"
            )

    async def process_notification(self, notification):
        if not isinstance(notification, PCSSequenceItem):
            raise TypeError(
                f"PCS model expects PCSSequenceItem notifications, got "
                f"{type(notification).__name__}"
            )

        contributes_payload = (not bool(notification.idle)) and bool(notification.tvalid)
        if contributes_payload:
            num_valid_bytes = self._num_valid_bytes_from_tkeep(notification.tkeep)
            if num_valid_bytes == 0:
                raise ValueError("Valid AXI beats must contain at least one valid byte")
            valid_bytes = self._extract_valid_bytes(notification.tdata, num_valid_bytes)
        else:
            valid_bytes = b""

        activity = AxiActivityRecord(
            activity_index=self._activity_index,
            sim_time_ns=current_time_ns(),
            idle=bool(notification.idle),
            tvalid=self._logic_to_int(notification.tvalid),
            tkeep=self._logic_to_int(notification.tkeep),
            tlast=self._logic_to_int(notification.tlast),
            out_ready=self._logic_to_int(notification.out_ready),
            valid_bytes=valid_bytes,
            contributes_payload=contributes_payload,
        )
        self._activity_index += 1
        self._recent_activity.append(activity)

        if not contributes_payload:
            if self._in_frame:
                self._current_frame_trace.append(activity)
            return

        if not self._in_frame:
            self._in_frame = True
            self._current_frame_trace = list(self._recent_activity)[:-1]
            self._current_payload_beats = []

        self._current_frame.extend(valid_bytes)
        self._current_frame_trace.append(activity)
        self._current_payload_beats.append(activity)

        if bool(notification.tlast):
            frame_record = ExpectedFrameRecord(
                frame_index=self._frame_index,
                payload=bytes(self._current_frame),
                payload_beats=tuple(self._current_payload_beats),
                trace=bounded_trace(self._current_frame_trace),
            )
            await self.expected_queue.put(frame_record)
            self._current_frame.clear()
            self._current_frame_trace = []
            self._current_payload_beats = []
            self._in_frame = False
            self._frame_index += 1

    @property
    def recent_activity(self) -> tuple[AxiActivityRecord, ...]:
        return tuple(self._recent_activity)
