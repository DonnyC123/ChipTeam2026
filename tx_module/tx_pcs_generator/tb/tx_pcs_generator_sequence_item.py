from dataclasses import dataclass, field
from typing import Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class TxPcsGeneratorSequenceItem(AbstractTransaction):
    DATA_W = 64
    KEEP_W = 8

    in_data_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxPcsGeneratorSequenceItem.DATA_W)
    )
    in_keep_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxPcsGeneratorSequenceItem.KEEP_W)
    )
    in_last_i: Logic = field(default_factory=lambda: Logic("0"))
    in_valid_i: Logic = field(default_factory=lambda: Logic("0"))
    out_ready_i: Logic = field(default_factory=lambda: Logic("1"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            in_data_i=LogicArray(0, cls.DATA_W),
            in_keep_i=LogicArray(0, cls.KEEP_W),
            in_last_i=Logic(0),
            in_valid_i=Logic(0),
            out_ready_i=Logic(1),
        )

    @property
    def valid(self) -> bool:
        return bool(self.in_valid_i)

    @property
    def to_data(self):
        return None
