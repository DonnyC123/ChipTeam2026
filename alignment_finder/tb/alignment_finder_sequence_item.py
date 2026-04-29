from dataclasses import dataclass, field
from typing import Self
from cocotb.types import Logic, LogicArray
from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class AlignmentFinderSequenceItem(AbstractTransaction):
    data_valid_i: Logic = field(default_factory=lambda: Logic("0"))
    data_i: LogicArray = field(default_factory=lambda: LogicArray("0" * 66))

    @property
    def valid(self) -> bool:
        return bool(self.data_valid_i)

    @property
    def to_data(self):
        return int(self.data_i)

    @classmethod
    def invalid_seq_item(cls) -> Self:
        item = cls()
        item.data_valid_i = Logic(0)
        item.data_i = LogicArray("0" * 66)
        return item
    
