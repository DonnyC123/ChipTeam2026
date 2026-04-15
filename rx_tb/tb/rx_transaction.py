from dataclasses import dataclass, field
from cocotb.types import Logic, LogicArray
from typing import Self
from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class RxTransaction(AbstractTransaction):
    out_data_o:    LogicArray = field(default_factory=lambda: LogicArray("0" * 64))
    bytes_valid_o: LogicArray = field(default_factory=lambda: LogicArray("0" * 8))
    out_valid_o:   Logic      = field(default_factory=lambda: Logic("0"))

    @property
    def valid(self) -> bool:
        return bool(self.out_valid_o)

    @property
    def valid_bytes(self) -> list[int]:
        mask  = int(self.bytes_valid_o)
        raw   = int(self.out_data_o).to_bytes(8, "little")
        return [raw[i] for i in range(0,8,1) if (mask >> i) & 1]

    @property
    def n_valid(self) -> int:
        return bin(int(self.bytes_valid_o)).count("1")

    @property
    def to_data(self):
        return self

    @classmethod
    def invalid_seq_item(cls) -> Self:
        item = cls()
        item.out_valid_o = Logic(0)
        return item