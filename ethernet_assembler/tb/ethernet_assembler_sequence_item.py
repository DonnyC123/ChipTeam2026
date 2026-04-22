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

    # Signals for the DUT
    input_data_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * EthernetAssemblerSequenceItem.DATA_IN_W)
    )
    header_bits_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * EthernetAssemblerSequenceItem.HEADER_W)
    )
    in_valid_i: Logic = field(default_factory=lambda: Logic("0"))
    locked_i: Logic = field(default_factory=lambda: Logic("0"))
    cancel_frame_i: Logic = field(default_factory=lambda: Logic("0"))

    # Flags for the model
    no_valid_data: Logic = field(
        default_factory=lambda: Logic("0"),
        metadata={"model_only": True},
    )
    drop_frame: Logic = field(
        default_factory=lambda: Logic("0"),
        metadata={"model_only": True},
    )

    def __post_init__(self):
        try:
            raw_payload = int(self.input_data_i)
            raw_header = int(self.header_bits_i)
        except (TypeError, ValueError):
            return

        raw_payload &= self.PAYLOAD_MASK
        raw_header &= self.HEADER_MASK
        self.input_data_i = LogicArray.from_unsigned(raw_payload, self.DATA_IN_W)
        self.header_bits_i = LogicArray.from_unsigned(raw_header, self.HEADER_W)

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
            no_valid_data=Logic(0),
            drop_frame=Logic(0),
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
            "no_valid_data": bool(self._to_int(self.no_valid_data, 0)),
            "drop_frame": bool(self._to_int(self.drop_frame, 0)),
        }
