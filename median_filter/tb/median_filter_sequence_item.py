from dataclasses import dataclass, field
from typing import Self
from cocotb.types import Logic
from tb_utils.abstract_transactions import AbstractValidTransaction
from .pixel_interface_transaction import PixelInterfaceTransaction


@dataclass
class MedianFilterSequenceItem(AbstractValidTransaction):
    start_i: Logic = field(default_factory=lambda: Logic("0"))

    pixel_valid_if_i: PixelInterfaceTransaction = field(
        default_factory=PixelInterfaceTransaction
    )

    @property
    def valid(self) -> bool:
        return bool(self.pixel_valid_if_i.valid)

    @valid.setter
    def valid(self, value: bool) -> None:
        self.pixel_valid_if_i.valid = Logic(value)

    @property
    def to_data(self):
        return self.pixel_valid_if_i.pixel.value_tuple

    @classmethod
    def invalid_seq_item(cls) -> Self:
        item = cls()
        item.start_i = Logic(0)
        item.pixel_valid_if_i.valid = Logic(0)
        return item
