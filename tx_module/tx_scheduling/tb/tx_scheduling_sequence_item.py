from dataclasses import dataclass, field
from typing import Self
from cocotb.types import Logic, LogicArray
from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class TxSchedulingSequenceItem(AbstractTransaction):
    NUM_QUEUES = 2
    QID_W = 1

    q_valid_i: LogicArray = field(
        default_factory=lambda: LogicArray(0, TxSchedulingSequenceItem.NUM_QUEUES)
    )
    q_last_i: LogicArray = field(
        default_factory=lambda: LogicArray(0, TxSchedulingSequenceItem.NUM_QUEUES)
    )
    fifo_full_i: Logic = field(default_factory=lambda: Logic("0"))
    fifo_grant_i: Logic = field(default_factory=lambda: Logic("1"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            q_valid_i=LogicArray(0, cls.NUM_QUEUES),
            q_last_i=LogicArray(0, cls.NUM_QUEUES),
            fifo_full_i=Logic(0),
            fifo_grant_i=Logic(1),
        )

    @property
    def valid(self) -> bool:
        try:
            return self.q_valid_i.to_unsigned() != 0
        except (ValueError, TypeError):
            return False

    @property
    def to_data(self):
        pass

    @valid.setter
    def valid(self, value: bool):
        pass
