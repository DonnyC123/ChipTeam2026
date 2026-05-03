from dataclasses import dataclass, field
from cocotb.types import Logic, LogicArray
from tb_utils.abstract_transactions import AbstractTransaction
from typing import Self


@dataclass
class RxSequenceItem(AbstractTransaction):
    raw_data_i:  LogicArray = field(default_factory=lambda: LogicArray("0" * 64))
    raw_valid_i: Logic      = field(default_factory=lambda: Logic("1"))

    @property
    def valid(self) -> bool:
        return bool(self.raw_valid_i)
    
    @property
    def to_data(self):
        return self

    @classmethod
    def from_int(cls, value: int, valid: bool = True) -> "RxSequenceItem":
        return cls(
            raw_data_i  = LogicArray.from_unsigned(value & 0xFFFFFFFFFFFFFFFF, 64),
            raw_valid_i = Logic(1 if valid else 0),
        )

    @classmethod
    def bubble(cls) -> "RxSequenceItem":
        return cls(
            raw_data_i  = LogicArray("0" * 64),
            raw_valid_i = Logic(0),
        )

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            raw_data_i  = LogicArray("0" * 64),
            raw_valid_i = Logic(0),
        )