from dataclasses import dataclass, field
from typing import Self

from cocotb.types import Logic

from tb_utils.abstract_transactions import AbstractValidTransaction

from .pixel_interface_transaction import PixelInterfaceTransaction


@dataclass
class MedianFilterOutTransaction(AbstractValidTransaction):
    pixel_valid_if_o: PixelInterfaceTransaction = field(
        default_factory=PixelInterfaceTransaction
    )

    @property
    def valid(self) -> bool:
        return bool(self.pixel_valid_if_o.valid)

    @valid.setter
    def valid(self, value: bool) -> None:
        self.pixel_valid_if_o.valid = Logic(value)

    @property
    def to_data(self):
        return self.pixel_valid_if_o.pixel.value_tuple

    @classmethod
    def invalid_seq_item(cls) -> Self:
        item = cls()
        item.pixel_valid_if_o.valid = Logic(0)
        return item
