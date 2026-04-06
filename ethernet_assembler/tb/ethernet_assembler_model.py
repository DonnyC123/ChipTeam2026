from typing import Any, Dict, Mapping, Tuple

from tb_utils.generic_model import GenericModel

# Ethernet 'Assembler' Planning:
# NOTE: The sequence item/transaction files dont exist yet.

# Inputs:
# - 64 bits of input_data payload
# - 2 bits of header_bits carrying the 64b/66b sync header
# - an bool in_valid signal which indicates if input_data is valid
# - a 'locked' bool signals which indicates that we are able to process our data

# Outputs: 
# - A bool out_valid signal that indicates if any of the output bytes are valid
# - 64 bits called out_data (payload transformed back from network bit order)
# - an array of 8 data_valid signals (bools) which indicate which bytes of out_data are valid

# Functionaility:
# - We need to parse the control bits from header_bits
# - If those bits are equal to 10 this is a control payload, and we need to check the first byte of the data (bits 63:56) to decide what to do
#     - We reference the 64/66b chart to decide if this is a start/end/idle frame
#     - We set the data_valid array based on that
#     - We need a variale to track wether we are inside of a frame, that gets set/changed
# - else If those bits are == 01 this is a data frame, and if we are inside a frame, then we can set all of the data_valid signals to high

# NETWORK ORDER: BIG ENDIAN 
# NETWORK ORDER: THE LSB is first ex.) 0x8 becomes 0x1

class EthernetAssemblerModel(GenericModel):
    DATA_SYNC_HEADER    = 0b01
    CONTROL_SYNC_HEADER = 0b10
    DATA_MASK_64        = (1 << 64) - 1
    BIT_REVERSE_TABLE   = tuple(int(f"{i:08b}"[::-1], 2) for i in range(256))
    IDLE_BLOCK_TYPE     = 0x1E

    # Start blocks (64b/66b control block type in byte [63:56]).
    START_VALID_MASKS: Dict[int, Tuple[bool, ...]] = {
        # Start in lane 0: byte0 is /S/, bytes1..7 are payload.
        0x78: (False, True, True, True, True, True, True, True),
        # Start in lane 4: byte4 is /S/, bytes5..7 are payload.
        0x33: (False, False, False, False, False, True, True, True),
    }

    # Terminate blocks
    END_VALID_MASKS: Dict[int, Tuple[bool, ...]] = {
        0x87: (False, False, False, False, False, False, False, False),  # T0
        0x99: (False, True, False, False, False, False, False, False),   # T1
        0xAA: (False, True, True, False, False, False, False, False),    # T2
        0xB4: (False, True, True, True, False, False, False, False),     # T3
        0xCC: (False, True, True, True, True, False, False, False),      # T4
        0xD2: (False, True, True, True, True, True, False, False),       # T5
        0xE1: (False, True, True, True, True, True, True, False),        # T6
        0xFF: (False, True, True, True, True, True, True, True),         # T7
    }

    # Non-payload control blocks that still carry data bytes.
    NON_PAYLOAD_CONTROL_TYPES: Dict[int, Tuple[bool, ...]] = {
        0x66: (False, True, True, True, False, True, True, True),  
        0x55: (False, True, True, True, False, True, True, True),   
        0x4B: (False, True, True, True, False, False, False, False),
        0x2D: (False, False, False, False, False, True, True, True),    
    }
    VALID_SYNC_HEADERS = {DATA_SYNC_HEADER, CONTROL_SYNC_HEADER}

    def __init__(self):
        super().__init__()
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

    @classmethod
    def _classify_block(cls, sync_header: int, block_type: int) -> str:
        if sync_header == cls.DATA_SYNC_HEADER:
            return "data"

        if sync_header != cls.CONTROL_SYNC_HEADER:
            return "bad_header"

        if block_type in cls.START_VALID_MASKS:
            return "start"
        if block_type in cls.END_VALID_MASKS:
            return "term"
        if block_type in cls.NON_PAYLOAD_CONTROL_TYPES:
            return "ordered_set"
        if block_type == cls.IDLE_BLOCK_TYPE:
            return "idle"
        return "unknown_control"

    def _decode_block(
        self,
        input_data: int,
        header_bits: int,
        in_valid: bool,
        locked: bool,
        cancel_frame: bool,
    ) -> Dict[str, Any]:
        raw_payload = input_data & self.DATA_MASK_64
        # Input payload is network-order (LSB-first on the wire). Convert back to regular bit order.
        out_data = self._reverse_bits(raw_payload, 64)
        data_valid = [False] * 8

        # header_bits arrives in network order at the DUT interface; convert to
        # internal order before block-type classification.
        sync_header = ((header_bits & 0b01) << 1) | ((header_bits >> 1) & 0b01)
        block_type = (out_data >> 56) & 0xFF
        block_class = self._classify_block(sync_header=sync_header, block_type=block_type)

        # Cancel seen while frame is active: flush current frame and enter drop mode.
        if self.in_frame and cancel_frame:
            self.in_frame = False
            self.drop_mode = True
            return {"out_valid": False, "out_data": out_data, "data_valid": data_valid}

        # Drop mode suppresses all blocks until cancel is low and a fresh SOF arrives.
        if self.drop_mode:
            self.in_frame = False
            if (
                (not cancel_frame)
                and in_valid
                and locked
                and block_class == "start"
            ):
                data_valid = list(self.START_VALID_MASKS[block_type])
                self.in_frame = True
                self.drop_mode = False

            out_valid = any(data_valid)
            return {"out_valid": out_valid, "out_data": out_data, "data_valid": data_valid}

        # Cancel asserted while idle: suppress output until cancel deasserts.
        if cancel_frame:
            self.in_frame = False
            return {"out_valid": False, "out_data": out_data, "data_valid": data_valid}

        # Match RTL ordering: while in-frame, bad sync header or lock loss drops
        # even if in_valid is low.
        if self.in_frame and (
            (not locked)
            or (sync_header not in self.VALID_SYNC_HEADERS)
        ):
            self.in_frame = False
            return {"out_valid": False, "out_data": out_data, "data_valid": data_valid}

        if not in_valid or not locked:
            return {"out_valid": False, "out_data": out_data, "data_valid": data_valid}

        if block_class == "bad_header":
            if self.in_frame:
                self.in_frame = False
            return {"out_valid": False, "out_data": out_data, "data_valid": data_valid}

        if block_class == "data":
            if self.in_frame:
                data_valid = [True] * 8
            out_valid = any(data_valid)
            return {"out_valid": out_valid, "out_data": out_data, "data_valid": data_valid}

        if block_class == "start":
            if self.in_frame:
                # Nested start is treated as corruption: abort and wait for fresh SOF.
                self.in_frame = False
            else:
                data_valid = list(self.START_VALID_MASKS[block_type])
                self.in_frame = True

            out_valid = any(data_valid)
            return {"out_valid": out_valid, "out_data": out_data, "data_valid": data_valid}

        if block_class == "term":
            if self.in_frame:
                data_valid = list(self.END_VALID_MASKS[block_type])
            self.in_frame = False
            out_valid = any(data_valid)
            return {"out_valid": out_valid, "out_data": out_data, "data_valid": data_valid}

        if block_class == "ordered_set":
            if self.in_frame:
                data_valid = list(self.NON_PAYLOAD_CONTROL_TYPES[block_type])
            out_valid = any(data_valid)
            return {"out_valid": out_valid, "out_data": out_data, "data_valid": data_valid}

        # IDLE or unknown control: ignore out-of-frame, abort in-frame.
        if self.in_frame:
            self.in_frame = False

        out_valid = any(data_valid)
        return {"out_valid": out_valid, "out_data": out_data, "data_valid": data_valid}

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
        in_valid = self._to_bool(
            notification.get("in_valid", notification.get("valid")), default=True
        )
        locked = self._to_bool(
            notification.get("locked", notification.get("locked_i")), default=True
        )
        cancel_frame = self._to_bool(
            notification.get("cancel_frame", notification.get("cancel_frame_i")),
            default=False,
        )

        expected = self._decode_block(
            input_data=input_data,
            header_bits=header_bits,
            in_valid=in_valid,
            locked=locked,
            cancel_frame=cancel_frame,
        )
        if expected["out_valid"]:
            await self.expected_queue.put(expected)
