from dataclasses import dataclass, field
from cocotb.types import Logic, LogicArray
from tb_utils.abstract_transactions import AbstractTransaction
from typing import Self


@dataclass
class FastMultiplierOutTransaction(AbstractTransaction):
    DOUT_W = 16

    data_o: LogicArray = field(
        default_factory=lambda: LogicArray("X" * FastMultiplierOutTransaction.DOUT_W)
    )

    product_valid_o: Logic = field(default_factory=lambda: Logic("X"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(product_valid_o=Logic(0))

    @property
    def valid(self) -> bool:
        return bool(self.product_valid_o)

    @valid.setter
    def valid(self, value: bool):
        self.product_valid_o = Logic(value)
