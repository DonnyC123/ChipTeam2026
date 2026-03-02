from dataclasses import dataclass, field
from typing import Self
from cocotb.types import Logic, LogicArray
from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class TxSchedulingOutTransaction(AbstractTransaction):
    QID_W = 1

    dma_read_en_o: Logic = field(default_factory=lambda: Logic("0"))
    dma_queue_sel_o: LogicArray = field(
        default_factory=lambda: LogicArray(0, TxSchedulingOutTransaction.QID_W)
    )
    fifo_req_o: Logic = field(default_factory=lambda: Logic("0"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls()

    @property
    def valid(self) -> bool:
        try:
            return bool(self.dma_read_en_o)
        except (ValueError, TypeError):
            return False

    @property
    def to_data(self):
        try:
            return self.dma_queue_sel_o.to_unsigned()
        except (ValueError, TypeError):
            return 0

    @valid.setter
    def valid(self, value: bool):
        self.dma_read_en_o = Logic(value)
