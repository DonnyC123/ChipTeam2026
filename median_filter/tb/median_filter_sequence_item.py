from dataclasses import dataclass, field
from typing import Self, Tuple

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class MedianFilterSequenceItem(AbstractTransaction):
    PIXEL_W = 8

    #Initialize defaults
    start_i: Logic = field(default_factory=lambda: Logic("X"))
    valid_i: Logic = field(default_factory=lambda: Logic("X"))
    red_i: LogicArray = field(default_factory=lambda: LogicArray("X" * MedianFilterSequenceItem.PIXEL_W))
    green_i: LogicArray = field(default_factory=lambda: LogicArray("X" * MedianFilterSequenceItem.PIXEL_W))
    blue_i: LogicArray = field(default_factory=lambda: LogicArray("X" * MedianFilterSequenceItem.PIXEL_W))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            start_i=Logic(0),
            valid_i=Logic(0),
            red_i=LogicArray("0" * cls.PIXEL_W),
            green_i=LogicArray("0" * cls.PIXEL_W),
            blue_i=LogicArray("0" * cls.PIXEL_W),
        )


    @property
    def valid(self) -> bool:
        return bool(self.valid_i)

    @valid.setter
    def valid(self, value: bool):
        self.valid_i = Logic(int(value))

    @property
    def rgb(self) -> Tuple[int, int, int]:
        return (int(self.red_i), int(self.green_i), int(self.blue_i))

    @property
    def to_data(self) -> bool:
        return self.valid

    @property
    def is_start(self) -> bool:
        return bool(self.start_i)
