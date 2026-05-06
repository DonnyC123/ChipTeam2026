from dataclasses import dataclass, field
from typing import Self
from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractValidTransaction


@dataclass
class TxSubsystemSequenceItem(AbstractValidTransaction):
    DMA_DATA_W = 256
    DMA_KEEP_W = 32

    s_axis_dma_tdata_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSubsystemSequenceItem.DMA_DATA_W)
    )
    s_axis_dma_tkeep_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSubsystemSequenceItem.DMA_KEEP_W)
    )
    s_axis_dma_tvalid_i: Logic = field(default_factory=lambda: Logic("0"))
    s_axis_dma_tlast_i: Logic = field(default_factory=lambda: Logic("0"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            s_axis_dma_tdata_i=LogicArray(0, cls.DMA_DATA_W),
            s_axis_dma_tkeep_i=LogicArray(0, cls.DMA_KEEP_W),
            s_axis_dma_tvalid_i=Logic(0),
            s_axis_dma_tlast_i=Logic(0),
        )

    @property
    def valid(self) -> bool:
        try:
            return bool(self.s_axis_dma_tvalid_i)
        except (TypeError, ValueError):
            return False

    @valid.setter
    def valid(self, value: bool):
        self.s_axis_dma_tvalid_i = Logic(1 if value else 0)

    @property
    def to_data(self):
        return None
