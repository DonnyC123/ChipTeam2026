from dataclasses import dataclass, field
from typing import Self, Tuple

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class MedianFilterOutTransaction(AbstractTransaction):
    PIXEL_W = 8

    red_o: LogicArray = field(default_factory=lambda: LogicArray("X" * MedianFilterOutTransaction.PIXEL_W))
    green_o: LogicArray = field(default_factory=lambda: LogicArray("X" * MedianFilterOutTransaction.PIXEL_W))
    blue_o: LogicArray = field(default_factory=lambda: LogicArray("X" * MedianFilterOutTransaction.PIXEL_W))

    valid_o: Logic = field(default_factory=lambda: Logic("0"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(valid_o=Logic(0))

    @property
    def valid(self) -> bool:
        return bool(self.valid_o)

    @valid.setter
    def valid(self, value: bool):
        self.valid_o = Logic(int(value))

    @property
    def rgb(self) -> Tuple[int, int, int]:
        return (int(self.red_o), int(self.green_o), int(self.blue_o))

    @property
    def to_data(self) -> Tuple[int, int, int]:
        return self.rgb

