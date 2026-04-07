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
        pass

    @valid.setter
    def valid(self, value: bool):
        pass
