from dataclasses import dataclass, field
from typing import Self
from cocotb.types import Logic, LogicArray
from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class TxFifoOutTransaction(AbstractTransaction):
    PCS_DATA_W = 64
    PCS_VALID_W = 8

    pcs_data_o: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxFifoOutTransaction.PCS_DATA_W)
    )
    pcs_valid_o: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxFifoOutTransaction.PCS_VALID_W)
    )
    pcs_last_o: Logic = field(default_factory=lambda: Logic("0"))
    pcs_read_i: Logic = field(default_factory=lambda: Logic("0"))
    empty_o: Logic = field(default_factory=lambda: Logic("1"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls()

    @property
    def valid(self) -> bool:
        try:
            return bool(self.pcs_read_i) and not bool(self.empty_o)
        except (ValueError, TypeError):
            return False

    @property
    def to_data(self):
        try:
            d = self.pcs_data_o.to_unsigned()
        except (ValueError, TypeError):
            d = 0
        try:
            v = self.pcs_valid_o.to_unsigned()
        except (ValueError, TypeError):
            v = 0
        try:
            l = 1 if bool(self.pcs_last_o) else 0
        except (ValueError, TypeError):
            l = 0
        return (d, v, l)

    @valid.setter
    def valid(self, value: bool):
        pass
