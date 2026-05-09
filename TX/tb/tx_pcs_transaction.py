from dataclasses import dataclass, field
from typing import Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractValidTransaction


@dataclass
class TxPcsTransaction(AbstractValidTransaction):
    pcs_data_o: LogicArray = field(default_factory=lambda: LogicArray("0" * 64))
    pcs_control_o: LogicArray = field(default_factory=lambda: LogicArray("0" * 2))
    pcs_valid_o: Logic = field(default_factory=lambda: Logic("0"))

    @property
    def valid(self) -> bool:
        try:
            return bool(self.pcs_valid_o)
        except (TypeError, ValueError):
            return False

    @valid.setter
    def valid(self, value: bool):
        self.pcs_valid_o = Logic(1 if value else 0)

    @property
    def to_data(self):
        try:
            return int(self.pcs_control_o), int(self.pcs_data_o)
        except (TypeError, ValueError):
            return 0, 0

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(pcs_valid_o=Logic(0))
