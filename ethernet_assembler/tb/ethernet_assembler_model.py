from typing import Any, Dict, Mapping, Tuple

from tb_utils.generic_model import GenericModel

# Ethernet 'Assembler' Planning:
# NOTE: The sequence item/transaction files dont exist yet.

# Inputs:
# - 66 bits of input_data (the MSB and MSB-1 are control signals, rest is data)
# - an bool in_valid signal which indicates if input_data is valid
# - a 'locked' bool signals which indicates that we are able to process our data

# Outputs: 
# - A bool out_valid signal that indicates if any of the output bytes are valid
# - 64 bits called out_data (which is the input 66 minus the 2 control bits)
# - an array of 8 data_valid signals (bools) which indicate which bytes of out_data are valid

# Functionaility:
# - We need to parse the control bits (the MSB and MSB-1) from input_data
# - If those bits are equal to 10 this is a control payload, and we need to check the first byte of the data (bits 63:56) to decide what to do
#     - We reference the 64/66b chart to decide if this is a start/end/idle frame
#     - We set the data_valid array based on that
#     - We need a variale to track wether we are inside of a frame, that gets set/changed
# - else If those bits are == 01 this is a data frame, and if we are inside a frame, then we can set all of the data_valid signals to high

# TODO: we need to flip all the bits as well
# NETWORK ORDER: BIG ENDIAN 
# NETWORK ORDER: THE LSB is first ex.) 0x8 becomes 0x1

class EthernetAssemblerModel(GenericModel):
    DATA_SYNC_HEADER    = 0b01
    CONTROL_SYNC_HEADER = 0b10
    DATA_MASK_64        = (1 << 64) - 1

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
        0x99: (True, False, False, False, False, False, False, False),   # T1
        0xAA: (True, True, False, False, False, False, False, False),    # T2
        0xB4: (True, True, True, False, False, False, False, False),     # T3
        0xCC: (True, True, True, True, False, False, False, False),      # T4
        0xD2: (True, True, True, True, True, False, False, False),       # T5
        0xE1: (True, True, True, True, True, True, False, False),        # T6
        0xFF: (True, True, True, True, True, True, True, False),         # T7
    }

    # Common idle / non-payload control blocks.
    IDLE_BLOCK_TYPES = {0x1E}
    NON_PAYLOAD_CONTROL_TYPES = {0x2D, 0x4B, 0x55, 0x66}

    def __init__(self):
        super().__init__()
        self.in_frame = False

    def _reset(self):
        self.in_frame = False

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
        reversed_value = 0
        for bit_idx in range(width):
            reversed_value = (reversed_value << 1) | ((value >> bit_idx) & 1)
        return reversed_value

    def _decode_block(self, input_data: int, in_valid: bool, locked: bool) -> Dict[str, Any]:
        raw_payload = input_data & self.DATA_MASK_64
        # Input payload is network-order (LSB-first on the wire). Convert back to regular bit order.
        out_data = self._reverse_bits(raw_payload, 64)
        data_valid = [False] * 8

        if not in_valid or not locked:
            return {"out_valid": False, "out_data": out_data, "data_valid": data_valid}

        sync_header = (input_data >> 64) & 0b11

        if sync_header == self.DATA_SYNC_HEADER:
            if self.in_frame:
                data_valid = [True] * 8
        elif sync_header == self.CONTROL_SYNC_HEADER:
            block_type = (out_data >> 56) & 0xFF

            if block_type in self.START_VALID_MASKS:
                data_valid = list(self.START_VALID_MASKS[block_type])
                self.in_frame = True
            elif block_type in self.END_VALID_MASKS:
                if self.in_frame:
                    data_valid = list(self.END_VALID_MASKS[block_type])
                self.in_frame = False
            elif block_type in self.IDLE_BLOCK_TYPES:
                self.in_frame = False
            elif block_type in self.NON_PAYLOAD_CONTROL_TYPES:
                pass
            else:
                # Unknown control block: emit no payload and preserve frame state.
                pass

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
        in_valid = self._to_bool(
            notification.get("in_valid", notification.get("valid")), default=True
        )
        locked = self._to_bool(
            notification.get("locked", notification.get("locked_i")), default=True
        )

        expected = self._decode_block(input_data=input_data, in_valid=in_valid, locked=locked)
        await self.expected_queue.put(expected)
