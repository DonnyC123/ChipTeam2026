from dataclasses import dataclass, field
from typing import Any, Dict, Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class EthernetAssemblerSequenceItem(AbstractTransaction):
    HEADER_W = 2
    DATA_IN_W = 64
    PAYLOAD_W = DATA_IN_W
    HEADER_MASK = (1 << HEADER_W) - 1
    PAYLOAD_MASK = (1 << DATA_IN_W) - 1
    BIT_REVERSE_TABLE = tuple(int(f"{i:08b}"[::-1], 2) for i in range(256))

    input_data_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * EthernetAssemblerSequenceItem.DATA_IN_W)
    )
    header_bits_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * EthernetAssemblerSequenceItem.HEADER_W)
    )
    in_valid_i: Logic = field(default_factory=lambda: Logic("0"))
    locked_i: Logic = field(default_factory=lambda: Logic("1"))
    cancel_frame_i: Logic = field(default_factory=lambda: Logic("0"))

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
    def _to_network_header(cls, header_bits: int) -> int:
        header_bits &= cls.HEADER_MASK
        # DUT expects network-order header bits.
        return ((header_bits & 0b01) << 1) | ((header_bits >> 1) & 0b01)

    @classmethod
    def _to_network_payload(cls, input_data: int) -> int:
        input_data &= cls.PAYLOAD_MASK
        # DUT expects network-order payload bits (bit-reversed within each byte).
        return cls._reverse_bits(input_data, cls.PAYLOAD_W)

    @classmethod
    def _to_network_order(
        cls, input_data: int, header_bits: int | None = None
    ) -> tuple[int, int]:
        # Backward compatible fallback: if header_bits is omitted, derive it from
        # packed input_data[65:64] from legacy callers.
        if header_bits is None:
            header_bits = (input_data >> cls.DATA_IN_W) & cls.HEADER_MASK
        payload = input_data & cls.PAYLOAD_MASK
        return cls._to_network_payload(payload), cls._to_network_header(header_bits)

    def __post_init__(self):
        try:
            raw_payload = int(self.input_data_i)
            raw_header = int(self.header_bits_i)
        except (TypeError, ValueError):
            return

        network_payload, network_header = self._to_network_order(raw_payload, raw_header)
        self.input_data_i = LogicArray.from_unsigned(network_payload, self.DATA_IN_W)
        self.header_bits_i = LogicArray.from_unsigned(network_header, self.HEADER_W)

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
            header_bits_i=LogicArray("0" * cls.HEADER_W),
            in_valid_i=Logic(0),
            locked_i=Logic(1),
            cancel_frame_i=Logic(0),
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
            "header_bits": self._to_int(self.header_bits_i, 0),
            "in_valid": bool(self._to_int(self.in_valid_i, 0)),
            "locked": bool(self._to_int(self.locked_i, 1)),
            "cancel_frame": bool(self._to_int(self.cancel_frame_i, 0)),
        }
