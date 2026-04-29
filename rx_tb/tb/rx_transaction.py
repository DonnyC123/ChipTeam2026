from dataclasses import dataclass, field
from cocotb.types import Logic, LogicArray
from typing import Self
from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class RxTransaction(AbstractTransaction):
    data_o:  LogicArray = field(default_factory=lambda: LogicArray("0" * 64))
    mask_o:  LogicArray = field(default_factory=lambda: LogicArray("0" * 8))
    valid_o: Logic      = field(default_factory=lambda: Logic("0"))
    send_o:  Logic      = field(default_factory=lambda: Logic("0"))
    drop_o:  Logic      = field(default_factory=lambda: Logic("0"))

    @property
    def valid(self) -> bool:
        return bool(self.valid_o)

    @property
    def send(self) -> bool:
        return bool(self.send_o)

    @property
    def drop(self) -> bool:
        return bool(self.drop_o)

    @property
    def valid_bytes(self) -> list[int]:
        mask = int(self.mask_o)
        raw  = int(self.data_o).to_bytes(8, "little")
        return [raw[i] for i in range(8) if (mask >> i) & 1]

    @property
    def n_valid(self) -> int:
        return bin(int(self.mask_o)).count("1")

    @property
    def to_data(self):
        return self

    @classmethod
    def invalid_seq_item(cls) -> Self:
        item = cls()
        item.valid_o = Logic(0)
        item.send_o  = Logic(0)
        item.drop_o  = Logic(0)
        return item