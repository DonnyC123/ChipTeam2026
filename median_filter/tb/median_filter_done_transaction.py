from dataclasses import dataclass, field
from cocotb.types import Logic
from tb_utils.abstract_transactions import AbstractTransaction
from typing import Self


@dataclass
class MedianFilterDoneTransaction(AbstractTransaction):
    done_o: Logic = field(default_factory=lambda: Logic("0"))

    @property
    def to_data(self):
        return self.done_o.to_unsigned()

    @classmethod
    def invalid_seq_item(cls) -> Self:
        pass
