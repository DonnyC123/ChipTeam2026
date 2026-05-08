from dataclasses import dataclass, field
from cocotb.types import Logic
from typing import Self

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class RxTransaction(AbstractTransaction):
    checksum_drop_o: Logic = field(default_factory=lambda: Logic("0"))
    parser_valid_o:  Logic = field(default_factory=lambda: Logic("0"))

    @property
    def valid(self) -> bool:
        return bool(self.parser_valid_o)

    @property
    def dropped(self) -> bool:
        return bool(self.checksum_drop_o)

    @property
    def to_data(self):
        return self

    @classmethod
    def invalid_seq_item(cls) -> Self:
        item = cls()
        item.checksum_drop_o = Logic("0")
        return item