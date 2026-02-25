from dataclasses import dataclass, field
from typing import Any, Dict, Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class EthernetAssemblerSequenceItem(AbstractTransaction):
    DATA_IN_W = 66

    input_data_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * EthernetAssemblerSequenceItem.DATA_IN_W)
    )
    in_valid_i: Logic = field(default_factory=lambda: Logic("0"))
    locked_i: Logic = field(default_factory=lambda: Logic("1"))

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
