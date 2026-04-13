from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

from tb_utils.generic_model import GenericModel


@dataclass(frozen=True)
class ControlBlockSpec:
    kind: str
    valid_mask: Tuple[bool, ...]
    enters_frame: bool = False
    exits_frame: bool = False


class EthernetAssemblerModel(GenericModel):
    DATA_SYNC_HEADER = 0b01
    CONTROL_SYNC_HEADER = 0b10
    DATA_MASK_64 = (1 << 64) - 1
    BIT_REVERSE_TABLE = tuple(int(f"{i:08b}"[::-1], 2) for i in range(256))
    VALID_SYNC_HEADERS = {DATA_SYNC_HEADER, CONTROL_SYNC_HEADER}

    CONTROL_BLOCK_LUT: Dict[int, ControlBlockSpec] = {
        # Start blocks.
        0x78: ControlBlockSpec(
            kind="start",
            valid_mask=(False, True, True, True, True, True, True, True),
            enters_frame=True,
        ),
        0x33: ControlBlockSpec(
            kind="start",
            valid_mask=(False, False, False, False, False, True, True, True),
            enters_frame=True,
        ),
        # Terminate blocks.
        0x87: ControlBlockSpec(
            kind="term",
            valid_mask=(False, False, False, False, False, False, False, False),
            exits_frame=True,
        ),
        0x99: ControlBlockSpec(
            kind="term",
            valid_mask=(False, True, False, False, False, False, False, False),
            exits_frame=True,
        ),
        0xAA: ControlBlockSpec(
            kind="term",
            valid_mask=(False, True, True, False, False, False, False, False),
            exits_frame=True,
        ),
        0xB4: ControlBlockSpec(
            kind="term",
            valid_mask=(False, True, True, True, False, False, False, False),
            exits_frame=True,
        ),
        0xCC: ControlBlockSpec(
            kind="term",
            valid_mask=(False, True, True, True, True, False, False, False),
            exits_frame=True,
        ),
        0xD2: ControlBlockSpec(
            kind="term",
            valid_mask=(False, True, True, True, True, True, False, False),
            exits_frame=True,
        ),
        0xE1: ControlBlockSpec(
            kind="term",
            valid_mask=(False, True, True, True, True, True, True, False),
            exits_frame=True,
        ),
        0xFF: ControlBlockSpec(
            kind="term",
            valid_mask=(False, True, True, True, True, True, True, True),
            exits_frame=True,
        ),
        # Ordered set blocks.
        0x66: ControlBlockSpec(
            kind="ordered_set",
            valid_mask=(False, True, True, True, False, True, True, True),
        ),
        0x55: ControlBlockSpec(
            kind="ordered_set",
            valid_mask=(False, True, True, True, False, True, True, True),
        ),
        0x4B: ControlBlockSpec(
            kind="ordered_set",
            valid_mask=(False, True, True, True, False, False, False, False),
        ),
        0x2D: ControlBlockSpec(
            kind="ordered_set",
            valid_mask=(False, False, False, False, False, True, True, True),
        ),
        # Idle block.
        0x1E: ControlBlockSpec(
            kind="idle",
            valid_mask=(False, False, False, False, False, False, False, False),
        ),
    }

    def __init__(self, cycle_accurate: bool = False):
        super().__init__()
        self.cycle_accurate = cycle_accurate
        self.in_frame = False
        self.drop_mode = False

    def _reset(self):
        self.in_frame = False
        self.drop_mode = False

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        if value is None:
            return default
        return int(value)

    @staticmethod
    def _to_bool(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        return bool(int(value))

    @staticmethod
    def _reverse_bits(value: int, width: int) -> int:
        if width <= 0:
            return 0

        value &= (1 << width) - 1
        reversed_value = 0
        full_bytes, remaining_bits = divmod(width, 8)

        for byte_idx in range(full_bytes):
            shift = byte_idx * 8
            byte = (value >> shift) & 0xFF
            reversed_value |= EthernetAssemblerModel.BIT_REVERSE_TABLE[byte] << shift

        if remaining_bits:
            shift = full_bytes * 8
            rem_mask = (1 << remaining_bits) - 1
            rem_bits = (value >> shift) & rem_mask
            rem_reversed = 0
            for bit_idx in range(remaining_bits):
                rem_reversed = (rem_reversed << 1) | ((rem_bits >> bit_idx) & 1)
            reversed_value |= rem_reversed << shift

        return reversed_value

    @staticmethod
    def _from_network_header(header_bits: int) -> int:
        header_bits &= 0b11
        return ((header_bits & 0b01) << 1) | ((header_bits >> 1) & 0b01)

    def _decode_baseline(
        self,
        *,
        input_data: int,
        header_bits: int,
        in_valid: bool,
        locked: bool,
        cancel_frame: bool,
    ) -> Dict[str, Any]:
        raw_payload = input_data & self.DATA_MASK_64
        out_data = self._reverse_bits(raw_payload, 64)
        sync_header = self._from_network_header(header_bits)
        control_byte = (out_data >> 56) & 0xFF

        expected = {
            "out_valid": False,
            "out_data": out_data,
            "data_valid": [False] * 8,
            "drop_frame": False,
        }

        was_in_frame = self.in_frame
        was_drop_mode = self.drop_mode
        next_in_frame = was_in_frame
        next_drop_mode = was_drop_mode

        can_read = in_valid and locked and (not cancel_frame)

        # Cancel while in-frame aborts the frame and enters drop mode.
        if was_in_frame and cancel_frame:
            expected["drop_frame"] = True
            next_in_frame = False
            next_drop_mode = True

        # Drop mode suppresses output until an uncanceled SOF is received.
        elif was_drop_mode:
            next_in_frame = False
            if can_read and sync_header == self.CONTROL_SYNC_HEADER:
                block_spec = self.CONTROL_BLOCK_LUT.get(control_byte)
                if block_spec is not None and block_spec.enters_frame:
                    expected["data_valid"] = list(block_spec.valid_mask)
                    next_in_frame = True
                    next_drop_mode = False
                else:
                    next_in_frame = False
                    next_drop_mode = True

        # In-frame lock loss or bad header is a drop only when input is valid.
        elif was_in_frame and in_valid and ((not locked) or (sync_header not in self.VALID_SYNC_HEADERS)):
            expected["drop_frame"] = True
            next_in_frame = False

        # Idle-state control handling.
        elif can_read and (not was_in_frame) and sync_header == self.CONTROL_SYNC_HEADER:
            block_spec = self.CONTROL_BLOCK_LUT.get(control_byte)
            if block_spec is not None and block_spec.enters_frame:
                expected["data_valid"] = list(block_spec.valid_mask)
                next_in_frame = True
            else:
                next_in_frame = False

        # In-frame control handling.
        elif can_read and was_in_frame and sync_header == self.CONTROL_SYNC_HEADER:
            block_spec = self.CONTROL_BLOCK_LUT.get(control_byte)
            if block_spec is None:
                expected["drop_frame"] = True
                next_in_frame = False
            elif block_spec.kind == "term":
                expected["data_valid"] = list(block_spec.valid_mask)
                if block_spec.exits_frame:
                    next_in_frame = False
            elif block_spec.kind == "ordered_set":
                expected["data_valid"] = list(block_spec.valid_mask)
            else:
                # Start/idle/other control while in-frame is treated as corruption.
                expected["drop_frame"] = True
                next_in_frame = False

        # In-frame data block.
        elif can_read and sync_header == self.DATA_SYNC_HEADER and was_in_frame:
            expected["data_valid"] = [True] * 8

        expected["out_valid"] = any(expected["data_valid"])
        self.in_frame = next_in_frame
        self.drop_mode = next_drop_mode
        return expected

    def _apply_metadata_overrides(
        self,
        *,
        expected: Dict[str, Any],
        no_valid_data: bool,
        drop_frame: bool,
    ):
        # drop_frame metadata dominates no_valid_data metadata.
        if drop_frame:
            expected["drop_frame"] = True
            expected["data_valid"] = [False] * 8
            expected["out_valid"] = False
            self.in_frame = False
            self.drop_mode = True
            return

        if no_valid_data:
            expected["data_valid"] = [False] * 8
            expected["out_valid"] = False

    async def process_notification(self, notification):
        if not isinstance(notification, Mapping):
            return

        event = notification.get("event")
        if event in {"reset", "start"}:
            self._reset()
            return

        input_data = self._to_int(
            notification.get(
                "input_data",
                notification.get("in_data", notification.get("data_i", notification.get("data"))),
            )
        )
        header_bits = self._to_int(
            notification.get("header_bits", notification.get("header_bits_i")),
            default=(input_data >> 64) & 0b11,
        )
        in_valid = self._to_bool(notification.get("in_valid", notification.get("valid")), default=True)
        locked = self._to_bool(notification.get("locked", notification.get("locked_i")), default=True)
        cancel_frame = self._to_bool(
            notification.get("cancel_frame", notification.get("cancel_frame_i")),
            default=False,
        )
        no_valid_data = self._to_bool(
            notification.get("no_valid_data", notification.get("no_valid_data_i")),
            default=False,
        )
        drop_frame = self._to_bool(
            notification.get("drop_frame", notification.get("drop_frame_i")),
            default=False,
        )

        expected = self._decode_baseline(
            input_data=input_data,
            header_bits=header_bits,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )
        self._apply_metadata_overrides(
            expected=expected,
            no_valid_data=no_valid_data,
            drop_frame=drop_frame,
        )

        if self.cycle_accurate or expected["out_valid"]:
            await self.expected_queue.put(expected)
