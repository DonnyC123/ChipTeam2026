from dataclasses import dataclass, field
from typing import Any, Dict, Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class EthernetParserSequenceItem(AbstractTransaction):
    DATA_IN_W = 64
    BYTES_OUT = 8
    OUTPUTS_W = 3

    OUTPUT_IPV4 = 0
    OUTPUT_IPV6 = 1
    OUTPUT_OTHER = 2

    bytes_valid_i: LogicArray = field(
        default_factory=lambda: LogicArray(
            "X" * EthernetParserSequenceItem.BYTES_OUT
        )
    )
    data_i: LogicArray = field(
        default_factory=lambda: LogicArray(
            "X" * EthernetParserSequenceItem.DATA_IN_W
        )
    )
    data_valid_i: Logic = field(default_factory=lambda: Logic("0"))
    expected_outputs_o: LogicArray = field(
        default_factory=lambda: LogicArray(
            "X" * EthernetParserSequenceItem.OUTPUTS_W
        ),
        metadata={"model_only": True},
    )

    def __post_init__(self):
        for field_name, width in (
            ("bytes_valid_i", self.BYTES_OUT),
            ("data_i", self.DATA_IN_W),
            ("expected_outputs_o", self.OUTPUTS_W),
        ):
            value = getattr(self, field_name)
            try:
                raw_value = int(value)
            except (TypeError, ValueError):
                continue

            mask = (1 << width) - 1
            setattr(self, field_name, LogicArray.from_unsigned(raw_value & mask, width))

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            bytes_valid_i=LogicArray("0" * cls.BYTES_OUT),
            data_i=LogicArray("0" * cls.DATA_IN_W),
            data_valid_i=Logic(0),
            expected_outputs_o=LogicArray.from_unsigned(
                cls.OUTPUT_OTHER, cls.OUTPUTS_W
            ),
        )

    @property
    def valid(self) -> bool:
        return bool(self._to_int(self.data_valid_i, 0))

    @valid.setter
    def valid(self, value: bool):
        self.data_valid_i = Logic(value)

    @property
    def to_data(self) -> Dict[str, Any]:
        return {
            "bytes_valid": self._to_int(self.bytes_valid_i, 0),
            "data": self._to_int(self.data_i, 0),
            "data_valid": bool(self._to_int(self.data_valid_i, 0)),
            "expected_outputs_o": self._to_int(
                self.expected_outputs_o, self.OUTPUT_OTHER
            ),
        }
