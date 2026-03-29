from dataclasses import dataclass, field
from typing import Any, Dict, List, Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class EthernetAssemblerTransaction(AbstractTransaction):
    DATA_OUT_W = 64
    BYTES_OUT = DATA_OUT_W // 8

    out_valid_o: Logic = field(default_factory=lambda: Logic("0"))
    out_data_o: LogicArray = field(
        default_factory=lambda: LogicArray("X" * EthernetAssemblerTransaction.DATA_OUT_W)
    )
    bytes_valid_o: LogicArray = field(
        default_factory=lambda: LogicArray("X" * EthernetAssemblerTransaction.BYTES_OUT)
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
            out_valid_o=Logic(0),
            out_data_o=LogicArray("0" * cls.DATA_OUT_W),
            bytes_valid_o=LogicArray("0" * cls.BYTES_OUT),
        )

    @property
    def valid(self) -> bool:
        return bool(self._to_int(self.out_valid_o, 0))

    @valid.setter
    def valid(self, value: bool):
        self.out_valid_o = Logic(value)

    @property
    def data_valid(self) -> List[bool]:
        bytes_valid = self._to_int(self.bytes_valid_o, 0)
        return [
            bool((bytes_valid >> (self.BYTES_OUT - 1 - idx)) & 1)
            for idx in range(self.BYTES_OUT)
        ]

    @property
    def to_data(self) -> Dict[str, Any]:
        return {
            "out_valid": self.valid,
            "out_data": self._to_int(self.out_data_o, 0),
            "data_valid": self.data_valid,
        }
