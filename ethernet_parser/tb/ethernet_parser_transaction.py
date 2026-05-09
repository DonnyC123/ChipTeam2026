from dataclasses import dataclass, field
from typing import Any, Dict, Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class EthernetParserTransaction(AbstractTransaction):
    OUTPUTS_W = 3

    valid_o: Logic = field(default_factory=lambda: Logic("0"))
    payload_time_o: Logic = field(default_factory=lambda: Logic("0"))
    outputs_o: LogicArray = field(
        default_factory=lambda: LogicArray("X" * EthernetParserTransaction.OUTPUTS_W)
    )

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            valid_o=Logic(0),
            payload_time_o=Logic(0),
            outputs_o=LogicArray("0" * cls.OUTPUTS_W),
        )

    @property
    def valid(self) -> bool:
        return bool(self._to_int(self.valid_o, 0))

    @valid.setter
    def valid(self, value: bool):
        self.valid_o = Logic(value)

    @property
    def to_data(self) -> Dict[str, Any]:
        return {
            "payload_time_o": self._to_int(self.payload_time_o, 0),
            "outputs_o": self._to_int(self.outputs_o, 0),
        }
