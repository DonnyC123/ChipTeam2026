from dataclasses import dataclass, field
from typing import Self
from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractValidTransaction


@dataclass
class TxSubsystemOutTransaction(AbstractValidTransaction):
    PCS_DATA_W = 64
    PCS_VALID_W = 8

    m_axis_tdata_o: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSubsystemOutTransaction.PCS_DATA_W)
    )
    m_axis_tkeep_o: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxSubsystemOutTransaction.PCS_VALID_W)
    )
    m_axis_tlast_o: Logic = field(default_factory=lambda: Logic("0"))
    m_axis_tvalid_o: Logic = field(default_factory=lambda: Logic("0"))
    m_axis_tready_i: Logic = field(default_factory=lambda: Logic("0"))

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls()

    @property
    def valid(self) -> bool:
        try:
            return bool(self.m_axis_tvalid_o) and bool(self.m_axis_tready_i)
        except (ValueError, TypeError):
            return False

    @property
    def to_data(self):
        try:
            data = self.m_axis_tdata_o.to_unsigned()
        except (ValueError, TypeError):
            data = 0
        try:
            keep = self.m_axis_tkeep_o.to_unsigned()
        except (ValueError, TypeError):
            keep = 0
        try:
            last = int(bool(self.m_axis_tlast_o))
        except (ValueError, TypeError):
            last = 0
        return (data, keep, last)

    @valid.setter
    def valid(self, value: bool):
        pass
