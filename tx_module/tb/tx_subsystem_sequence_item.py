from dataclasses import dataclass, field
from typing import Self
from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class TxSubsystemSequenceItem(AbstractTransaction):
    DMA_DATA_W = 256
    DMA_VALID_W = 32
    NUM_QUEUES = 2

    q_valid_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSubsystemSequenceItem.NUM_QUEUES)
    )
    q_last_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSubsystemSequenceItem.NUM_QUEUES)
    )

    s_axis_dma_tdata_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSubsystemSequenceItem.DMA_DATA_W)
    )
    s_axis_dma_tkeep_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSubsystemSequenceItem.DMA_VALID_W)
    )
    s_axis_dma_tvalid_i: Logic = field(default_factory=lambda: Logic("0"))
    s_axis_dma_tlast_i: Logic = field(default_factory=lambda: Logic("0"))

    dma_req_ready_i: Logic = field(default_factory=lambda: Logic("1"))
    m_axis_tready_i: Logic = field(default_factory=lambda: Logic("1"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            q_valid_i=LogicArray(0, cls.NUM_QUEUES),
            q_last_i=LogicArray(0, cls.NUM_QUEUES),
            s_axis_dma_tdata_i=LogicArray(0, cls.DMA_DATA_W),
            s_axis_dma_tkeep_i=LogicArray(0, cls.DMA_VALID_W),
            s_axis_dma_tvalid_i=Logic(0),
            s_axis_dma_tlast_i=Logic(0),
            dma_req_ready_i=Logic(1),
            m_axis_tready_i=Logic(1),
        )

    @property
    def valid(self) -> bool:
        return bool(self.s_axis_dma_tvalid_i) or bool(self.q_valid_i.to_unsigned())

    @property
    def to_data(self):
        return None
