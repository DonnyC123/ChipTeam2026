import os
from dataclasses import dataclass, field
from typing import Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


def _positive_env_int(name: str, default: int) -> int:
    value = int(os.environ.get(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def _qid_width(num_queues: int) -> int:
    return max(1, (num_queues - 1).bit_length())


@dataclass
class TxSequenceItem(AbstractTransaction):
    DMA_DATA_W = 256
    DMA_KEEP_W = 32
    NUM_QUEUES = _positive_env_int("TX_TB_NUM_QUEUES", 4)
    QID_W = _qid_width(NUM_QUEUES)

    s_axis_dma_tdata_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSequenceItem.DMA_DATA_W)
    )
    s_axis_dma_tkeep_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSequenceItem.DMA_KEEP_W)
    )
    s_axis_dma_tvalid_i: Logic = field(default_factory=lambda: Logic("0"))
    s_axis_dma_tlast_i: Logic = field(default_factory=lambda: Logic("0"))
    s_axis_dma_tdest_i: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSequenceItem.QID_W)
    )

    @property
    def valid(self) -> bool:
        return bool(self.s_axis_dma_tvalid_i)

    @property
    def to_data(self):
        return self

    @classmethod
    def tdest_value(cls, tdest: int) -> LogicArray:
        if tdest < 0 or tdest >= cls.NUM_QUEUES:
            raise ValueError(
                f"tdest {tdest} is outside configured NUM_QUEUES={cls.NUM_QUEUES}"
            )
        return LogicArray.from_unsigned(tdest, cls.QID_W)

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            s_axis_dma_tdata_i=LogicArray(0, cls.DMA_DATA_W),
            s_axis_dma_tkeep_i=LogicArray(0, cls.DMA_KEEP_W),
            s_axis_dma_tvalid_i=Logic(0),
            s_axis_dma_tlast_i=Logic(0),
            s_axis_dma_tdest_i=LogicArray(0, cls.QID_W),
        )
