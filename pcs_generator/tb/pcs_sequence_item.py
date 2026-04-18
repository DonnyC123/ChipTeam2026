from dataclasses import dataclass, field
from cocotb.types import Logic, LogicArray
from tb_utils.abstract_transactions import AbstractTransaction
from typing import Self


@dataclass
class ByteValidSequenceItem(AbstractTransaction):
    byte_data: LogicArray = field(default_factory=lambda: LogicArray("X" * 8))
    byte_valid: Logic = field(default_factory=lambda: Logic("0"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(byte_valid=Logic(0))

    @property
    def valid(self) -> bool:
        return bool(self.data_valid)

    @valid.setter
    def valid(self, value: bool):
        self.data_valid = Logic(value)
