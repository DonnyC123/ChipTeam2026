from dataclasses import dataclass
from typing import Any, Optional, Type

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
        self._in_frame = False
        self._frame_index = 0
        self._awaiting_post_eof_idle = False
        self._idle_blocks_since_eof = 0
        self._frame_size_count = 0
        self._seen_any_frame = False

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
            completed_frame = self._process_block(decoded_block)
            if completed_frame is not None:
                await self.actual_queue.put(completed_frame)

    def _start_frame(self, decoded_block: DecodedPCSBlock) -> None:
        self._current_frame_payload.clear()
        self._current_frame_payload.extend(decoded_block.payload_bytes)
        self._frame_size_count = len(decoded_block.payload_bytes) + 1
        self._in_frame = True
        self._awaiting_post_eof_idle = False
        self._idle_blocks_since_eof = 0

    def _complete_frame(self, decoded_block: DecodedPCSBlock) -> bytes:
        self._current_frame_payload.extend(decoded_block.payload_bytes)
        self._frame_size_count += len(decoded_block.payload_bytes) + 1
        if self._frame_size_count < self.MIN_FRAME_SIZE:
            raise RuntimeError(
                f"Frame {self._frame_index} ended too early: size count "
                f"{self._frame_size_count} is below {self.MIN_FRAME_SIZE}"
            )

        completed_frame = bytes(self._current_frame_payload)
        self._current_frame_payload.clear()
        self._in_frame = False
        self._frame_index += 1
        self._awaiting_post_eof_idle = True
        self._idle_blocks_since_eof = 0
        self._frame_size_count = 0
        self._seen_any_frame = True
        return completed_frame

    def _process_block(self, decoded_block: DecodedPCSBlock) -> Optional[bytes]:
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
    ) -> Optional[bytes]:
        if decoded_block.is_idle:
            return None
        if decoded_block.is_sof_l0 or decoded_block.is_sof_l4:
            self._start_frame(decoded_block)
            return None

        raise RuntimeError(
            f"Before any frame has started, only IDLE_BLK, SOF_L0, or SOF_L4 are legal; "
            f"saw {decoded_block.name}"
        )

    def _process_post_eof_block(self, decoded_block: DecodedPCSBlock) -> Optional[bytes]:
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
            f"After EOF, only IDLE_BLK, SOF_L4, or SOF_L0 are legal; saw {decoded_block.name}"
        )

    def _process_in_frame_block(self, decoded_block: DecodedPCSBlock) -> Optional[bytes]:
        if decoded_block.is_idle:
            raise RuntimeError(f"IDLE_BLK is illegal inside frame {self._frame_index}")
        if decoded_block.is_sof_l0 or decoded_block.is_sof_l4:
            raise RuntimeError(
                f"{decoded_block.name} is illegal while frame {self._frame_index} is active"
            )

        if self._frame_size_count < self.MIN_TERM_ELIGIBLE_COUNT:
            if not decoded_block.is_data:
                raise RuntimeError(
                    f"Frame {self._frame_index} size count is {self._frame_size_count}; "
                    f"expected DATA_HDR before EOF eligibility, saw {decoded_block.name}"
                )
            self._current_frame_payload.extend(decoded_block.payload_bytes)
            self._frame_size_count += len(decoded_block.payload_bytes)
            return None

        if decoded_block.is_data:
            self._current_frame_payload.extend(decoded_block.payload_bytes)
            self._frame_size_count += len(decoded_block.payload_bytes)
            return None

        if decoded_block.is_term:
            return self._complete_frame(decoded_block)

        raise RuntimeError(
            f"Frame {self._frame_index} may only emit DATA_HDR or TERM_L* once EOF becomes "
            f"legal; saw {decoded_block.name}"
        )

    def assert_complete(self) -> None:
        if self._in_frame:
            raise RuntimeError(
                f"Monitor stopped while frame {self._frame_index} was still open"
            )
        if self._awaiting_post_eof_idle:
            raise RuntimeError(
                f"Monitor stopped before the mandatory post-EOF idle after frame "
                f"{self._frame_index - 1}"
            )
