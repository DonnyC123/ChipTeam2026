from dataclasses import dataclass, field
from typing import Self
from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class TxSubsystemSequenceItem(AbstractTransaction):
    DMA_DATA_W = 256
    DMA_VALID_W = 32
    NUM_QUEUES = 4
    QID_W = (NUM_QUEUES - 1).bit_length() if NUM_QUEUES > 1 else 1

    s_axis_dma_tdata_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSubsystemSequenceItem.DMA_DATA_W)
    )
    s_axis_dma_tkeep_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSubsystemSequenceItem.DMA_VALID_W)
    )
    s_axis_dma_tvalid_i: Logic = field(default_factory=lambda: Logic("0"))
    s_axis_dma_tlast_i: Logic = field(default_factory=lambda: Logic("0"))
    s_axis_dma_tdest_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSubsystemSequenceItem.QID_W)
    )
    m_axis_tready_i: Logic = field(default_factory=lambda: Logic("1"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            s_axis_dma_tdata_i=LogicArray(0, cls.DMA_DATA_W),
            s_axis_dma_tkeep_i=LogicArray(0, cls.DMA_VALID_W),
            s_axis_dma_tvalid_i=Logic(0),
            s_axis_dma_tlast_i=Logic(0),
            s_axis_dma_tdest_i=LogicArray(0, cls.QID_W),
            m_axis_tready_i=Logic(1),
        )

    @property
    def valid(self) -> bool:
        return bool(self.s_axis_dma_tvalid_i)

    @property
    def to_data(self):
        return None
