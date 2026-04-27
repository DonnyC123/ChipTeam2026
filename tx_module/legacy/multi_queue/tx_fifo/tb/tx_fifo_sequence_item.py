from dataclasses import dataclass, field
from typing import Self
from cocotb.types import Logic, LogicArray
from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class TxFifoSequenceItem(AbstractTransaction):
    DMA_DATA_W = 256
    DMA_VALID_W = 32

    dma_data_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * TxFifoSequenceItem.DMA_DATA_W)
    )
    dma_valid_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * TxFifoSequenceItem.DMA_VALID_W)
    )
    dma_last_i: Logic = field(default_factory=lambda: Logic("0"))
    dma_wr_en_i: Logic = field(default_factory=lambda: Logic("0"))
    pcs_read_i: Logic = field(default_factory=lambda: Logic("0"))
    sched_req_i: Logic = field(default_factory=lambda: Logic("0"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            dma_data_i=LogicArray(0, cls.DMA_DATA_W),
            dma_valid_i=LogicArray(0, cls.DMA_VALID_W),
            dma_last_i=Logic(0),
            dma_wr_en_i=Logic(0),
            pcs_read_i=Logic(0),
            sched_req_i=Logic(0),
        )

    @property
    def valid(self) -> bool:
        return bool(self.dma_wr_en_i) or bool(self.pcs_read_i)

    @property
    def to_data(self):
        try:
            data = self.dma_data_i.to_unsigned()
        except (TypeError, ValueError):
            data = 0
        try:
            valid = self.dma_valid_i.to_unsigned()
        except (TypeError, ValueError):
            valid = 0
        try:
            last = 1 if bool(self.dma_last_i) else 0
        except (TypeError, ValueError):
            last = 0
        return {
            "data": data,
            "valid": valid,
            "last": last,
            "write": bool(self.dma_wr_en_i),
            "read": bool(self.pcs_read_i),
            "sched_req": bool(self.sched_req_i),
        }

    @valid.setter
    def valid(self, value: bool):
        if not value:
            self.dma_wr_en_i = Logic(0)
            self.pcs_read_i = Logic(0)
            self.sched_req_i = Logic(0)
        elif not (bool(self.dma_wr_en_i) or bool(self.pcs_read_i)):
            self.dma_wr_en_i = Logic(1)
