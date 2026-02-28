from dataclasses import dataclass, field
from cocotb.types import Logic
from tb_utils.abstract_transactions import AbstractTransaction
from typing import Self

@dataclass
class AlignmentFinderOutTransaction(AbstractTransaction):
    data_valid_i: Logic = field(default_factory=lambda: Logic("0"))  # add this
    locked_o: Logic = field(default_factory=lambda: Logic("0"))
    bitslip_o: Logic = field(default_factory=lambda: Logic("0"))

    @property
    def valid(self) -> bool:
        return bool(self.data_valid_i)  # only capture when input is valid

    @property
    def to_data(self):
        return (
            int(self.locked_o),
            int(self.bitslip_o),
        )

    @classmethod
    def invalid_seq_item(cls) -> Self:
        item = cls()
        item.data_valid_i = Logic(0)
        item.locked_o = Logic(0)
        item.bitslip_o = Logic(0)
        return item