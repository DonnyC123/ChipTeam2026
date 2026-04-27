from dataclasses import dataclass, field
from typing import Self
from cocotb.types import Logic, LogicArray
from tb_utils.abstract_transactions import AbstractValidTransaction


@dataclass
class TxSchedulingSequenceItem(AbstractValidTransaction):
    NUM_QUEUES = 4
    QID_W = 2

    q_valid_i: LogicArray = field(
        default_factory=lambda: LogicArray(0, TxSchedulingSequenceItem.NUM_QUEUES)
    )
    q_last_i: LogicArray = field(
        default_factory=lambda: LogicArray(0, TxSchedulingSequenceItem.NUM_QUEUES)
    )
    q_packet_ready_i: LogicArray = field(
        default_factory=lambda: LogicArray(0, TxSchedulingSequenceItem.NUM_QUEUES)
    )
    fifo_full_i: Logic = field(default_factory=lambda: Logic("0"))
    fifo_grant_i: Logic = field(default_factory=lambda: Logic("1"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            q_valid_i=LogicArray(0, cls.NUM_QUEUES),
            q_last_i=LogicArray(0, cls.NUM_QUEUES),
            q_packet_ready_i=LogicArray(0, cls.NUM_QUEUES),
            fifo_full_i=Logic(0),
            fifo_grant_i=Logic(1),
        )

    @property
    def valid(self) -> bool:
        try:
            return (self.q_valid_i.to_unsigned() | self.q_packet_ready_i.to_unsigned()) != 0
        except (ValueError, TypeError):
            return False

    @property
    def to_data(self):
        try:
            q_valid = self.q_valid_i.to_unsigned()
        except (TypeError, ValueError):
            q_valid = 0
        try:
            q_last = self.q_last_i.to_unsigned()
        except (TypeError, ValueError):
            q_last = 0
        try:
            q_packet_ready = self.q_packet_ready_i.to_unsigned()
        except (TypeError, ValueError):
            q_packet_ready = q_valid
        try:
            fifo_full = 1 if bool(self.fifo_full_i) else 0
        except (TypeError, ValueError):
            fifo_full = 0
        try:
            fifo_grant = 1 if bool(self.fifo_grant_i) else 0
        except (TypeError, ValueError):
            fifo_grant = 0
        return {
            "q_valid": q_valid,
            "q_last": q_last,
            "q_packet_ready": q_packet_ready,
            "fifo_full": fifo_full,
            "fifo_grant": fifo_grant,
        }

    @valid.setter
    def valid(self, value: bool):
        if not value:
            self.q_valid_i = LogicArray(0, self.NUM_QUEUES)
            self.q_packet_ready_i = LogicArray(0, self.NUM_QUEUES)
        elif self.q_valid_i.to_unsigned() == 0:
            self.q_valid_i = LogicArray.from_unsigned(1, self.NUM_QUEUES)
            self.q_packet_ready_i = LogicArray.from_unsigned(1, self.NUM_QUEUES)
