from collections import deque
from dataclasses import dataclass
from typing import Any, Optional, Type

from pcs_generator.tb.pcs_debug import (
    ActualFrameRecord,
    DUTStateSnapshot,
    ObservedBlockRecord,
    STATE_NAMES,
    TRACE_HISTORY_DEPTH,
    bounded_trace,
    current_time_ns,
    format_hexdump,
    format_recent_records,
    indent_block,
    logic_to_int_or_none,
)
from pcs_generator.tb.pcs_transactions import PCSOutputBlockTransaction
from tb_utils.generic_monitor import GenericValidMonitor


@dataclass
class DecodedPCSBlock:
    header: int
    block_type: Optional[int]
    valid_mask: int
    payload_bytes: bytes
    is_data: bool
    is_idle: bool
    is_sof_l0: bool
    is_sof_l4: bool
    is_term: bool
    name: str


class PCSMonitor(GenericValidMonitor[PCSOutputBlockTransaction]):
    CTRL_HDR = 0b10
    DATA_HDR = 0b01

    IDLE_BLK = 0x1E
    SOF_L0 = 0x78
    SOF_L4 = 0x33
    TERM_L0 = 0x87
    TERM_L1 = 0x99
    TERM_L2 = 0xAA
    TERM_L3 = 0xB4
    TERM_L4 = 0xCC
    TERM_L5 = 0xD2
    TERM_L6 = 0xE1
    TERM_L7 = 0xFF
    OS_D6 = 0x66
    OS_D5 = 0x55
    OS_D3T = 0x4B
    OS_D3B = 0x2D

    DATA_VALID_MASK = 0xFF
    MIN_TERM_ELIGIBLE_COUNT = 56
    MIN_FRAME_SIZE = 64

    CONTROL_BLOCK_VALID_MASKS = {
        IDLE_BLK: 0x00,
        SOF_L0: 0xFE,
        SOF_L4: 0xE0,
        TERM_L0: 0x00,
        TERM_L1: 0x02,
        TERM_L2: 0x06,
        TERM_L3: 0x0E,
        TERM_L4: 0x1E,
        TERM_L5: 0x3E,
        TERM_L6: 0x7E,
        TERM_L7: 0xFE,
    }
    UNSUPPORTED_CONTROL_BLOCKS = {OS_D6, OS_D5, OS_D3T, OS_D3B}
    TERM_BLOCK_TYPES = {
        TERM_L0,
        TERM_L1,
        TERM_L2,
        TERM_L3,
        TERM_L4,
        TERM_L5,
        TERM_L6,
        TERM_L7,
    }
    BLOCK_NAMES = {
        IDLE_BLK: "IDLE_BLK",
        SOF_L0: "SOF_L0",
        SOF_L4: "SOF_L4",
        TERM_L0: "TERM_L0",
        TERM_L1: "TERM_L1",
        TERM_L2: "TERM_L2",
        TERM_L3: "TERM_L3",
        TERM_L4: "TERM_L4",
        TERM_L5: "TERM_L5",
        TERM_L6: "TERM_L6",
        TERM_L7: "TERM_L7",
        OS_D6: "OS_D6",
        OS_D5: "OS_D5",
        OS_D3T: "OS_D3T",
        OS_D3B: "OS_D3B",
    }

    def __init__(
        self,
        dut,
        output_transaction: Type[PCSOutputBlockTransaction] = PCSOutputBlockTransaction,
    ):
        self._reset_protocol_state()
        super().__init__(dut=dut, output_transaction=output_transaction)

    def _reset_protocol_state(self) -> None:
        self._current_frame_payload = bytearray()
        self._current_frame_blocks: list[ObservedBlockRecord] = []
        self._current_frame_leading_blocks: tuple[ObservedBlockRecord, ...] = ()
        self._in_frame = False
        self._frame_index = 0
        self._awaiting_post_eof_idle = False
        self._idle_blocks_since_eof = 0
        self._frame_size_count = 0
        self._seen_any_frame = False
        self._block_index = 0
        self._recent_blocks: deque[ObservedBlockRecord] = deque(maxlen=TRACE_HISTORY_DEPTH)
        self._missing_signal_paths: set[str] = set()

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
    def _extract_block_type(cls, out_data_o: Any) -> int:
        return cls._logic_to_int(out_data_o) & 0xFF

    @classmethod
    def _bytes_from_word_lsb_first(cls, out_data_o: Any) -> list[int]:
        word_int = cls._logic_to_int(out_data_o)
        return [
            (word_int >> (8 * byte_index)) & 0xFF
            for byte_index in range(PCSOutputBlockTransaction.NUM_BYTES)
        ]

    @classmethod
    def _apply_valid_mask(cls, out_data_o: Any, valid_mask: int) -> bytes:
        return bytes(
            byte_value
            for byte_index, byte_value in enumerate(cls._bytes_from_word_lsb_first(out_data_o))
            if valid_mask & (1 << byte_index)
        )

    @classmethod
    def _block_name(cls, block_type: int) -> str:
        return cls.BLOCK_NAMES.get(block_type, f"0x{block_type:02X}")

    @classmethod
    def _decode_raw_block(cls, raw_block: PCSOutputBlockTransaction) -> DecodedPCSBlock:
        header = cls._logic_to_int(raw_block.out_control_o)
        if header == cls.DATA_HDR:
            return DecodedPCSBlock(
                header=header,
                block_type=None,
                valid_mask=cls.DATA_VALID_MASK,
                payload_bytes=cls._apply_valid_mask(raw_block.out_data_o, cls.DATA_VALID_MASK),
                is_data=True,
                is_idle=False,
                is_sof_l0=False,
                is_sof_l4=False,
                is_term=False,
                name="DATA_HDR",
            )

        if header != cls.CTRL_HDR:
            raise RuntimeError(f"Illegal DUT header 0b{header:02b}")

        block_type = cls._extract_block_type(raw_block.out_data_o)
        if block_type in cls.UNSUPPORTED_CONTROL_BLOCKS:
            raise RuntimeError(f"Unsupported control block type {cls._block_name(block_type)}")
        if block_type not in cls.CONTROL_BLOCK_VALID_MASKS:
            raise RuntimeError(f"Unknown control block type 0x{block_type:02X}")

        valid_mask = cls.CONTROL_BLOCK_VALID_MASKS[block_type]
        return DecodedPCSBlock(
            header=header,
            block_type=block_type,
            valid_mask=valid_mask,
            payload_bytes=cls._apply_valid_mask(raw_block.out_data_o, valid_mask),
            is_data=False,
            is_idle=block_type == cls.IDLE_BLK,
            is_sof_l0=block_type == cls.SOF_L0,
            is_sof_l4=block_type == cls.SOF_L4,
            is_term=block_type in cls.TERM_BLOCK_TYPES,
            name=cls._block_name(block_type),
        )

    async def monitor_loop(self):
        while True:
            raw_block = await self.receive_transaction()
            decoded_block = self._decode_raw_block(raw_block)
            observed_block = self._build_observed_block(raw_block, decoded_block)
            self._recent_blocks.append(observed_block)
            completed_frame = self._process_block(decoded_block)
            if completed_frame is not None:
                await self.actual_queue.put(completed_frame)

    def _start_frame(self, decoded_block: DecodedPCSBlock) -> None:
        self._current_frame_payload.clear()
        self._current_frame_payload.extend(decoded_block.payload_bytes)
        self._current_frame_leading_blocks = bounded_trace(self._recent_blocks)
        if self._current_frame_leading_blocks:
            self._current_frame_leading_blocks = self._current_frame_leading_blocks[:-1]
        self._current_frame_blocks = [self._recent_blocks[-1]]
        self._frame_size_count = len(decoded_block.payload_bytes) + 1
        self._in_frame = True
        self._awaiting_post_eof_idle = False
        self._idle_blocks_since_eof = 0

    def _complete_frame(self, decoded_block: DecodedPCSBlock) -> ActualFrameRecord:
        self._current_frame_payload.extend(decoded_block.payload_bytes)
        self._frame_size_count += len(decoded_block.payload_bytes) + 1
        if self._frame_size_count < self.MIN_FRAME_SIZE:
            raise RuntimeError(
                f"Frame {self._frame_index} ended too early: size count "
                f"{self._frame_size_count} is below {self.MIN_FRAME_SIZE}\n"
                f"{self._format_inflight_frame_debug()}"
            )

        completed_frame = ActualFrameRecord(
            frame_index=self._frame_index,
            payload=bytes(self._current_frame_payload),
            blocks=tuple(self._current_frame_blocks),
            leading_blocks=self._current_frame_leading_blocks,
        )
        self._current_frame_payload.clear()
        self._current_frame_blocks = []
        self._current_frame_leading_blocks = ()
        self._in_frame = False
        self._frame_index += 1
        self._awaiting_post_eof_idle = True
        self._idle_blocks_since_eof = 0
        self._frame_size_count = 0
        self._seen_any_frame = True
        return completed_frame

    def _process_block(self, decoded_block: DecodedPCSBlock) -> Optional[ActualFrameRecord]:
        if self._in_frame:
            return self._process_in_frame_block(decoded_block)

        if self._awaiting_post_eof_idle:
            if not decoded_block.is_idle:
                raise RuntimeError(
                    f"Frame {self._frame_index} ended, so the next block must be IDLE_BLK; "
                    f"saw {decoded_block.name}"
                )
            self._idle_blocks_since_eof = 1
            self._awaiting_post_eof_idle = False
            return None

        if not self._seen_any_frame:
            return self._process_initial_outside_frame_block(decoded_block)

        return self._process_post_eof_block(decoded_block)

    def _process_initial_outside_frame_block(
        self, decoded_block: DecodedPCSBlock
    ) -> Optional[ActualFrameRecord]:
        if decoded_block.is_idle:
            return None
        if decoded_block.is_sof_l0 or decoded_block.is_sof_l4:
            self._start_frame(decoded_block)
            return None

        raise RuntimeError(
            f"Before any frame has started, only IDLE_BLK, SOF_L0, or SOF_L4 are legal; "
            f"saw {decoded_block.name}"
        )

    def _process_post_eof_block(
        self, decoded_block: DecodedPCSBlock
    ) -> Optional[ActualFrameRecord]:
        if decoded_block.is_idle:
            self._idle_blocks_since_eof += 1
            return None

        if decoded_block.is_sof_l4:
            if self._idle_blocks_since_eof < 1:
                raise RuntimeError("SOF_L4 is illegal before the mandatory post-EOF idle")
            if self._idle_blocks_since_eof > 2:
                raise RuntimeError(
                    f"SOF_L4 is illegal after {self._idle_blocks_since_eof} idle blocks"
                )
            self._start_frame(decoded_block)
            return None

        if decoded_block.is_sof_l0:
            if self._idle_blocks_since_eof < 1:
                raise RuntimeError("SOF_L0 is illegal before the mandatory post-EOF idle")
            self._start_frame(decoded_block)
            return None

        raise RuntimeError(
            f"After EOF, only IDLE_BLK, SOF_L4, or SOF_L0 are legal; saw {decoded_block.name}\n"
            f"Recent observed blocks:\n"
            f"{indent_block(format_recent_records(self.recent_blocks, empty_message='<empty>'))}"
        )

    def _process_in_frame_block(
        self, decoded_block: DecodedPCSBlock
    ) -> Optional[ActualFrameRecord]:
        if decoded_block.is_idle:
            raise RuntimeError(
                f"IDLE_BLK is illegal inside frame {self._frame_index}\n"
                f"{self._format_inflight_frame_debug()}"
            )
        if decoded_block.is_sof_l0 or decoded_block.is_sof_l4:
            raise RuntimeError(
                f"{decoded_block.name} is illegal while frame {self._frame_index} is active\n"
                f"{self._format_inflight_frame_debug()}"
            )

        if self._frame_size_count < self.MIN_TERM_ELIGIBLE_COUNT:
            if not decoded_block.is_data:
                raise RuntimeError(
                    f"Frame {self._frame_index} size count is {self._frame_size_count}; "
                    f"expected DATA_HDR before EOF eligibility, saw {decoded_block.name}\n"
                    f"{self._format_inflight_frame_debug()}"
                )
            self._current_frame_blocks.append(self._recent_blocks[-1])
            self._current_frame_payload.extend(decoded_block.payload_bytes)
            self._frame_size_count += len(decoded_block.payload_bytes)
            return None

        if decoded_block.is_data:
            self._current_frame_blocks.append(self._recent_blocks[-1])
            self._current_frame_payload.extend(decoded_block.payload_bytes)
            self._frame_size_count += len(decoded_block.payload_bytes)
            return None

        if decoded_block.is_term:
            self._current_frame_blocks.append(self._recent_blocks[-1])
            return self._complete_frame(decoded_block)

        raise RuntimeError(
            f"Frame {self._frame_index} may only emit DATA_HDR or TERM_L* once EOF becomes "
            f"legal; saw {decoded_block.name}\n"
            f"{self._format_inflight_frame_debug()}"
        )

    def assert_complete(self) -> None:
        if self._in_frame:
            raise RuntimeError(
                f"Monitor stopped while frame {self._frame_index} was still open\n"
                f"{self._format_inflight_frame_debug()}"
            )
        if self._awaiting_post_eof_idle:
            raise RuntimeError(
                f"Monitor stopped before the mandatory post-EOF idle after frame "
                f"{self._frame_index - 1}\n"
                f"Recent observed blocks:\n"
                f"{indent_block(format_recent_records(self.recent_blocks, empty_message='<empty>'))}"
            )

    @property
    def recent_blocks(self) -> tuple[ObservedBlockRecord, ...]:
        return tuple(self._recent_blocks)

    def _build_observed_block(
        self, raw_block: PCSOutputBlockTransaction, decoded_block: DecodedPCSBlock
    ) -> ObservedBlockRecord:
        observed_block = ObservedBlockRecord(
            block_index=self._block_index,
            sim_time_ns=current_time_ns(),
            name=decoded_block.name,
            header=self._logic_to_int(raw_block.out_control_o),
            raw_data=self._logic_to_int(raw_block.out_data_o),
            valid_mask=decoded_block.valid_mask,
            payload_bytes=decoded_block.payload_bytes,
            dut_state=self._capture_dut_state(),
        )
        self._block_index += 1
        return observed_block

    @staticmethod
    def _resolve_handle(base_handle, path: str):
        handle = base_handle
        for path_component in path.split("."):
            if not hasattr(handle, path_component):
                return None
            handle = getattr(handle, path_component)
        return handle

    def _read_optional_signal(self, *paths: str) -> Optional[int]:
        core_handle = getattr(self.dut, "dut", self.dut)
        for path in paths:
            if path in self._missing_signal_paths:
                continue
            signal_handle = self._resolve_handle(core_handle, path)
            if signal_handle is None:
                self._missing_signal_paths.add(path)
                continue
            value = logic_to_int_or_none(signal_handle.value)
            if value is not None:
                return value
        return None

    def _capture_dut_state(self) -> DUTStateSnapshot:
        state_value = self._read_optional_signal("current_state")
        if state_value is not None:
            current_state = STATE_NAMES.get(state_value, f"STATE_{state_value}")
        else:
            current_state = None

        return DUTStateSnapshot(
            current_state=current_state,
            held_byte_cnt=self._read_optional_signal("held_byte_cnt_q"),
            num_incoming=self._read_optional_signal("num_incoming_q"),
            axis_tvalid=self._read_optional_signal("axis_slave_if.tvalid"),
            axis_tkeep=self._read_optional_signal("axis_slave_if.tkeep"),
            axis_tlast=self._read_optional_signal("axis_slave_if.tlast"),
            axis_tready=self._read_optional_signal("axis_slave_if.tready"),
            out_ready=self._read_optional_signal("out_ready_i"),
            can_read=self._read_optional_signal("can_read"),
            get_axi=self._read_optional_signal("get_axi"),
            next_is_last=self._read_optional_signal("next_is_last"),
            skid_valid=self._read_optional_signal(
                "skid_value_q_valid_data_i",
                "skid_value_q.valid_data_i",
            ),
            skid_last=self._read_optional_signal(
                "skid_value_q_last_byte",
                "skid_value_q.last_byte",
            ),
            skid_tkeep=self._read_optional_signal(
                "skid_value_q_valid_bytes_mask",
                "skid_value_q.valid_bytes_mask",
            ),
            skid_data=self._read_optional_signal("skid_value_q_data", "skid_value_q.data"),
        )

    def _format_inflight_frame_debug(self) -> str:
        current_payload = bytes(self._current_frame_payload)
        lines = [
            f"Current partial payload length={len(current_payload)}",
            "Current partial payload hexdump:",
            indent_block(format_hexdump(current_payload)),
            "Current frame blocks:",
            indent_block(
                format_recent_records(
                    self._current_frame_blocks,
                    empty_message="<no frame blocks recorded>",
                )
            ),
            "Recent observed blocks:",
            indent_block(
                format_recent_records(
                    self.recent_blocks,
                    empty_message="<no observed blocks recorded>",
                )
            ),
        ]
        return "\n".join(lines)
