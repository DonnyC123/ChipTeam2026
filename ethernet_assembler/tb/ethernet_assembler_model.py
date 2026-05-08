from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

from tb_utils.generic_model import GenericModel


def _mask_from_bytes_valid(mask: int) -> Tuple[bool, ...]:
    return tuple(bool((mask >> (7 - idx)) & 1) for idx in range(8))


@dataclass(frozen=True)
class ControlBlockSpec:
    kind: str
    valid_mask: Tuple[bool, ...]
    enters_frame: bool = False
    exits_frame: bool = False


class EthernetAssemblerModel(GenericModel):
    # Sync headers in the same on-the-wire bit ordering the RTL uses
    # (LSB of the 66-bit slot is transmitted first). Per IEEE Cl. 49:
    #   control = wire 1,0 → 2'b01
    #   data    = wire 0,1 → 2'b10
    DATA_SYNC_HEADER = 0b10
    CONTROL_SYNC_HEADER = 0b01
    DATA_MASK_64 = (1 << 64) - 1
    IPG_MIN = 12
    IPG_IDLE_BYTES = 8
    SOF_L4_IPG_MIN = IPG_MIN - 4
    VALID_SYNC_HEADERS = {DATA_SYNC_HEADER, CONTROL_SYNC_HEADER}
    TERM_IPG_LUT = {
        0x87: 7,
        0x99: 6,
        0xAA: 5,
        0xB4: 4,
        0xCC: 3,
        0xD2: 2,
        0xE1: 1,
        0xFF: 0,
    }

    CONTROL_BLOCK_LUT: Dict[int, ControlBlockSpec] = {
        # Start blocks. Per IEEE Cl. 49 the SOF block carries the trailing
        # preamble+SFD bytes in lanes 1-7 (SOF_L0) or 5-7 (SOF_L4) — those
        # are NOT MAC frame data, so the assembler emits zero valid bytes
        # for the SOF block itself. The actual frame starts at lane 0 of
        # the next block.
        0x78: ControlBlockSpec(
            kind="start",
            valid_mask=_mask_from_bytes_valid(0b0000_0000),
            enters_frame=True,
        ),
        0x33: ControlBlockSpec(
            kind="start",
            valid_mask=_mask_from_bytes_valid(0b0000_0000),
            enters_frame=True,
        ),
        # Terminate blocks.
        0x87: ControlBlockSpec(
            kind="term",
            valid_mask=_mask_from_bytes_valid(0b0000_0000),
            exits_frame=True,
        ),
        0x99: ControlBlockSpec(
            kind="term",
            valid_mask=_mask_from_bytes_valid(0b0000_0010),
            exits_frame=True,
        ),
        0xAA: ControlBlockSpec(
            kind="term",
            valid_mask=_mask_from_bytes_valid(0b0000_0110),
            exits_frame=True,
        ),
        0xB4: ControlBlockSpec(
            kind="term",
            valid_mask=_mask_from_bytes_valid(0b0000_1110),
            exits_frame=True,
        ),
        0xCC: ControlBlockSpec(
            kind="term",
            valid_mask=_mask_from_bytes_valid(0b0001_1110),
            exits_frame=True,
        ),
        0xD2: ControlBlockSpec(
            kind="term",
            valid_mask=_mask_from_bytes_valid(0b0011_1110),
            exits_frame=True,
        ),
        0xE1: ControlBlockSpec(
            kind="term",
            valid_mask=_mask_from_bytes_valid(0b0111_1110),
            exits_frame=True,
        ),
        0xFF: ControlBlockSpec(
            kind="term",
            valid_mask=_mask_from_bytes_valid(0b1111_1110),
            exits_frame=True,
        ),
        # Ordered set blocks.
        0x66: ControlBlockSpec(
            kind="ordered_set",
            valid_mask=_mask_from_bytes_valid(0b1110_1110),
        ),
        0x55: ControlBlockSpec(
            kind="ordered_set",
            valid_mask=_mask_from_bytes_valid(0b1110_1110),
        ),
        0x4B: ControlBlockSpec(
            kind="ordered_set",
            valid_mask=_mask_from_bytes_valid(0b0000_1110),
        ),
        0x2D: ControlBlockSpec(
            kind="ordered_set",
            valid_mask=_mask_from_bytes_valid(0b1110_0000),
        ),
        # Idle block.
        0x1E: ControlBlockSpec(
            kind="idle",
            valid_mask=_mask_from_bytes_valid(0b0000_0000),
        ),
    }

    # SOF_L4-mode TERM masks (4-lane shift relative to SOF_L0). For TERM_L0..L4
    # the trailing buffer (4 prior MAC bytes) plus 0..4 TERM data bytes are
    # emitted in lanes 0..(3+x), giving contiguous masks 0x0F..0xFF.
    # TERM_L5..L7 in SOF_L4 mode aren't natively supported (would need >8
    # bytes in one beat) — RTL falls back to the legacy mask, model matches.
    SOF_L4_TERM_MASK = {
        0x87: 0b0000_1111,
        0x99: 0b0001_1111,
        0xAA: 0b0011_1111,
        0xB4: 0b0111_1111,
        0xCC: 0b1111_1111,
    }

    # Number of MAC data bytes carried in the TERM block at lanes 1..n.
    SOF_L4_TERM_LANES = {0x87: 0, 0x99: 1, 0xAA: 2, 0xB4: 3, 0xCC: 4}

    def __init__(self, cycle_accurate: bool = False):
        super().__init__()
        self.cycle_accurate = cycle_accurate
        self.in_frame = False
        self.drop_mode = False
        self.ipg_bytes = 0
        self.ipg_check_en = False
        # Mirrors RTL state added for QLogic-style SOF_L4 frames.
        self.sof_l4_active = False
        self.sof_l4_first_data = False
        self.sof_l4_buf = 0  # 32-bit; holds prior DATA's lanes 4-7

    def _reset(self):
        self.in_frame = False
        self.drop_mode = False
        self.ipg_bytes = 0
        self.ipg_check_en = False
        self.sof_l4_active = False
        self.sof_l4_first_data = False
        self.sof_l4_buf = 0

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

    @classmethod
    def _advance_ipg(cls, ipg_bytes: int, count: int) -> int:
        return min(cls.IPG_MIN, ipg_bytes + count)

    @classmethod
    def _start_ipg_met(cls, control_byte: int, ipg_bytes: int) -> bool:
        if control_byte == 0x78:
            return ipg_bytes >= cls.IPG_MIN
        if control_byte == 0x33:
            return ipg_bytes >= cls.SOF_L4_IPG_MIN
        return False

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
        out_data = raw_payload
        sync_header = header_bits & 0b11
        control_byte = out_data & 0xFF

        expected = {
            "out_valid": False,
            "out_data": out_data,
            "data_valid": [False] * 8,
            "drop_frame": False,
        }

        was_in_frame = self.in_frame
        was_drop_mode = self.drop_mode
        was_ipg_bytes = self.ipg_bytes
        was_ipg_check_en = self.ipg_check_en
        was_sof_l4_active = self.sof_l4_active
        was_sof_l4_first_data = self.sof_l4_first_data
        was_sof_l4_buf = self.sof_l4_buf
        next_in_frame = was_in_frame
        next_drop_mode = was_drop_mode
        next_ipg_bytes = was_ipg_bytes
        next_ipg_check_en = was_ipg_check_en
        next_sof_l4_active = was_sof_l4_active
        next_sof_l4_first_data = was_sof_l4_first_data
        next_sof_l4_buf = was_sof_l4_buf

        can_read = in_valid and locked and (not cancel_frame)

        # Cancel while in-frame aborts the frame and enters drop mode.
        if was_in_frame and cancel_frame:
            expected["drop_frame"] = True
            next_in_frame = False
            next_drop_mode = True
            next_ipg_bytes = 0
            next_sof_l4_active = False
            next_sof_l4_first_data = False

        # Drop mode suppresses output until an uncanceled SOF is received.
        elif was_drop_mode:
            next_in_frame = False
            if can_read and sync_header == self.CONTROL_SYNC_HEADER:
                block_spec = self.CONTROL_BLOCK_LUT.get(control_byte)
                if block_spec is not None and block_spec.kind == "idle":
                    next_ipg_bytes = self._advance_ipg(was_ipg_bytes, self.IPG_IDLE_BYTES)
                elif block_spec is not None and block_spec.enters_frame:
                    if (not was_ipg_check_en) or self._start_ipg_met(control_byte, was_ipg_bytes):
                        expected["data_valid"] = list(block_spec.valid_mask)
                        next_in_frame = True
                        next_drop_mode = False
                        next_ipg_bytes = 0
                        next_ipg_check_en = True
                        if control_byte == 0x33:  # SOF_L4
                            next_sof_l4_active = True
                            next_sof_l4_first_data = True
                    else:
                        expected["drop_frame"] = True
                        next_in_frame = False
                        next_drop_mode = True
                        next_ipg_bytes = 0
                else:
                    next_in_frame = False
                    next_drop_mode = True

        # In-frame lock loss or bad header is a drop only when input is valid.
        elif was_in_frame and in_valid and ((not locked) or (sync_header not in self.VALID_SYNC_HEADERS)):
            expected["drop_frame"] = True
            next_in_frame = False
            next_drop_mode = True
            next_ipg_bytes = 0
            next_sof_l4_active = False
            next_sof_l4_first_data = False

        # Idle-state control handling.
        elif can_read and (not was_in_frame) and sync_header == self.CONTROL_SYNC_HEADER:
            block_spec = self.CONTROL_BLOCK_LUT.get(control_byte)
            if block_spec is not None and block_spec.kind == "idle":
                next_ipg_bytes = self._advance_ipg(was_ipg_bytes, self.IPG_IDLE_BYTES)
            elif block_spec is not None and block_spec.enters_frame:
                if (not was_ipg_check_en) or self._start_ipg_met(control_byte, was_ipg_bytes):
                    expected["data_valid"] = list(block_spec.valid_mask)
                    next_in_frame = True
                    next_ipg_bytes = 0
                    next_ipg_check_en = True
                    if control_byte == 0x33:  # SOF_L4
                        next_sof_l4_active = True
                        next_sof_l4_first_data = True
                else:
                    expected["drop_frame"] = True
                    next_in_frame = False
                    next_drop_mode = True
                    next_ipg_bytes = 0
            else:
                next_in_frame = False

        # In-frame control handling.
        elif can_read and was_in_frame and sync_header == self.CONTROL_SYNC_HEADER:
            block_spec = self.CONTROL_BLOCK_LUT.get(control_byte)
            if block_spec is None:
                expected["drop_frame"] = True
                next_in_frame = False
                next_drop_mode = True
                next_ipg_bytes = 0
                next_sof_l4_active = False
                next_sof_l4_first_data = False
            elif block_spec.kind == "term":
                if was_sof_l4_active and control_byte in self.SOF_L4_TERM_MASK:
                    # SOF_L4 TERM: emit {term_data_lanes_1..n, sof_l4_buf}
                    # at lanes 0..(3+n). Mask shifted up by 4 lanes.
                    sof_l4_mask = self.SOF_L4_TERM_MASK[control_byte]
                    n = self.SOF_L4_TERM_LANES[control_byte]
                    expected["data_valid"] = list(_mask_from_bytes_valid(sof_l4_mask))
                    term_data = (input_data >> 8) & ((1 << (n * 8)) - 1) if n > 0 else 0
                    expected["out_data"] = ((term_data & 0xFFFFFFFF) << 32) | (was_sof_l4_buf & 0xFFFFFFFF)
                else:
                    # Legacy SOF_L0 path (or TERM_L5/L6/L7 in SOF_L4 mode —
                    # RTL falls back to legacy mask there).
                    expected["data_valid"] = list(block_spec.valid_mask)
                if block_spec.exits_frame:
                    next_in_frame = False
                    next_ipg_bytes = self.TERM_IPG_LUT[control_byte]
                    next_sof_l4_active = False
                    next_sof_l4_first_data = False
            elif block_spec.kind == "ordered_set":
                expected["data_valid"] = list(block_spec.valid_mask)
            else:
                # Start/idle/other control while in-frame is treated as corruption.
                expected["drop_frame"] = True
                next_in_frame = False
                next_drop_mode = True
                next_ipg_bytes = 0
                next_sof_l4_active = False
                next_sof_l4_first_data = False

        # In-frame data block.
        elif can_read and sync_header == self.DATA_SYNC_HEADER and was_in_frame:
            if was_sof_l4_active and was_sof_l4_first_data:
                # DATA1 after SOF_L4: lanes 0-3 are trailing preamble (drop),
                # lanes 4-7 are MAC[0..3] — buffer them, emit nothing.
                expected["data_valid"] = [False] * 8
                next_sof_l4_buf = (input_data >> 32) & 0xFFFFFFFF
                next_sof_l4_first_data = False
            elif was_sof_l4_active:
                # DATA2+ in SOF_L4: emit {input[31:0], sof_l4_buf} (lanes 0-3
                # = prior buffer, lanes 4-7 = current input lanes 0-3).
                # Buffer current input lanes 4-7 for next emission.
                expected["data_valid"] = [True] * 8
                expected["out_data"] = ((input_data & 0xFFFFFFFF) << 32) | (was_sof_l4_buf & 0xFFFFFFFF)
                next_sof_l4_buf = (input_data >> 32) & 0xFFFFFFFF
            else:
                expected["data_valid"] = [True] * 8

        expected["out_valid"] = any(expected["data_valid"])
        self.in_frame = next_in_frame
        self.drop_mode = next_drop_mode
        self.ipg_bytes = next_ipg_bytes
        self.ipg_check_en = next_ipg_check_en
        self.sof_l4_active = next_sof_l4_active
        self.sof_l4_first_data = next_sof_l4_first_data
        self.sof_l4_buf = next_sof_l4_buf
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
            self.ipg_bytes = 0
            self.ipg_check_en = True
            self.sof_l4_active = False
            self.sof_l4_first_data = False
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
            default=input_data & 0b11,
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
