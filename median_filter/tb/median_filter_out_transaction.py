from dataclasses import dataclass, field
from cocotb.types import Logic
from tb_utils.abstract_transactions import AbstractTransaction
from .pixel_interface_transaction import PixelInterfaceTransaction
from typing import Self


@dataclass
class MedianFilterOutTransaction(AbstractTransaction):
    done_o: Logic = field(default_factory=lambda: Logic("0"))

    pixel_valid_if_o: PixelInterfaceTransaction = field(
        default_factory=PixelInterfaceTransaction
    )

    @property
    def valid(self) -> bool:
        return bool(self.pixel_valid_if_o.valid)

    @property
    def to_data(self):
        return self.pixel_valid_if_o.pixel.value_tuple

    @classmethod
    def invalid_seq_item(cls) -> Self:
        item = cls()
        item.done_o = Logic(0)
        item.pixel_valid_if_o.valid = Logic(0)
        return item
