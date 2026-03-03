from dataclasses import dataclass, field
from typing import Any, Dict, Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class EthernetAssemblerSequenceItem(AbstractTransaction):
    DATA_IN_W = 66
    PAYLOAD_W = DATA_IN_W - 2
    PAYLOAD_MASK = (1 << PAYLOAD_W) - 1
    BIT_REVERSE_TABLE = tuple(int(f"{i:08b}"[::-1], 2) for i in range(256))

    input_data_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * EthernetAssemblerSequenceItem.DATA_IN_W)
    )
    in_valid_i: Logic = field(default_factory=lambda: Logic("0"))
    locked_i: Logic = field(default_factory=lambda: Logic("1"))

    @classmethod
    def _reverse_bits(cls, value: int, width: int) -> int:
        if width <= 0:
            return 0

        value &= (1 << width) - 1
        reversed_value = 0
        full_bytes, remaining_bits = divmod(width, 8)

        for byte_idx in range(full_bytes):
            shift = byte_idx * 8
            byte = (value >> shift) & 0xFF
            reversed_value |= cls.BIT_REVERSE_TABLE[byte] << shift

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
    def _to_network_order(cls, input_data: int) -> int:
        input_data &= (1 << cls.DATA_IN_W) - 1

        header = (input_data >> cls.PAYLOAD_W) & 0b11
        payload = input_data & cls.PAYLOAD_MASK

        # DUT expects network-order bits on input: swap 2-bit header order and
        # reverse bit order inside each payload byte.
        network_header = ((header & 0b01) << 1) | ((header >> 1) & 0b01)
        network_payload = cls._reverse_bits(payload, cls.PAYLOAD_W)

        return (network_header << cls.PAYLOAD_W) | network_payload

    def __post_init__(self):
        try:
            raw_input_data = int(self.input_data_i)
        except (TypeError, ValueError):
            return

        network_input_data = self._to_network_order(raw_input_data)
        self.input_data_i = LogicArray.from_unsigned(network_input_data, self.DATA_IN_W)

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except ValueError:
            return default

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            input_data_i=LogicArray("0" * cls.DATA_IN_W),
            in_valid_i=Logic(0),
            locked_i=Logic(1),
        )

    @property
    def valid(self) -> bool:
        return bool(self._to_int(self.in_valid_i, 0))

    @valid.setter
    def valid(self, value: bool):
        self.in_valid_i = Logic(value)

    @property
    def to_data(self) -> Dict[str, Any]:
        return {
            "input_data": self._to_int(self.input_data_i, 0),
            "in_valid": bool(self._to_int(self.in_valid_i, 0)),
            "locked": bool(self._to_int(self.locked_i, 1)),
        }
