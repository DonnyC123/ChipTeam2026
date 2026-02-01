from dataclasses import dataclass, field
from cocotb.types import Logic, LogicArray
from tb_utils.abstract_transactions import AbstractTransaction
from typing import Self


@dataclass
class FastMultiplierSequenceItem(AbstractTransaction):
    DIN_W = 8

    a_operand_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * FastMultiplierSequenceItem.DIN_W)
    )
    b_operand_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * FastMultiplierSequenceItem.DIN_W)
    )

    operands_valid_i: Logic = field(default_factory=lambda: Logic("X"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(operands_valid_i=Logic(0))

    @property
    def valid(self) -> bool:
        return bool(self.operands_valid_i)

    @valid.setter
    def valid(self, value: bool):
        self.operands_valid_i = Logic(value)
