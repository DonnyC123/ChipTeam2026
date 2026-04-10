from dataclasses import dataclass, field
from typing import Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class TxPcsGeneratorOutTransaction(AbstractTransaction):
    DATA_W = 64
    CONTROL_W = 2

    out_data_o: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxPcsGeneratorOutTransaction.DATA_W)
    )
    out_control_o: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxPcsGeneratorOutTransaction.CONTROL_W)
    )
    out_valid_o: Logic = field(default_factory=lambda: Logic("0"))
    out_ready_i: Logic = field(default_factory=lambda: Logic("1"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls()

    @property
    def valid(self) -> bool:
        try:
            return bool(self.out_valid_o) and bool(self.out_ready_i)
        except (ValueError, TypeError):
            return False

    @property
    def to_data(self):
        try:
            data = self.out_data_o.to_unsigned()
        except (ValueError, TypeError):
            data = 0
        try:
            control = self.out_control_o.to_unsigned()
        except (ValueError, TypeError):
            control = 0

        return (data, control)

    @valid.setter
    def valid(self, value: bool):
        pass
