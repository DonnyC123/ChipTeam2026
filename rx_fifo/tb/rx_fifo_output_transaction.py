from dataclasses import dataclass, field
from typing import Any, Dict, Self

from cocotb.types import Logic, LogicArray

from rx_fifo.tb.rx_fifo_sequence_item import RXFifoSequenceItem
from tb_utils.abstract_transactions import AbstractTransaction, AbstractValidTransaction


@dataclass
class AXIStreamOutputTransaction:
    data: LogicArray = field(
        default_factory=lambda: LogicArray("X" * RXFifoSequenceItem.DATA_OUT_W)
    )
    mask: LogicArray = field(
        default_factory=lambda: LogicArray("X" * RXFifoSequenceItem.OUT_MASK_W)
    )
    valid: Logic = field(default_factory=lambda: Logic("0"))
    last: Logic = field(default_factory=lambda: Logic("0"))


@dataclass
class RXFifoOutputTransaction(AbstractTransaction):
    m_axi: AXIStreamOutputTransaction = field(
        default_factory=AXIStreamOutputTransaction
    )

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except ValueError:
            return default

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            m_axi=AXIStreamOutputTransaction(
                valid=Logic(0),
                last=Logic(0),
            )
        )

    @property
    def valid(self) -> bool:
        return bool(self._to_int(self.m_axi.valid, 0))

    @valid.setter
    def valid(self, value: bool):
        self.m_axi.valid = Logic(value)

    @property
    def to_data(self) -> Dict[str, Any]:
        return {
            "data": self._to_int(self.m_axi.data, 0),
            "last_mask": self._to_int(self.m_axi.mask, 0) & 0xFF,
            "last": bool(self._to_int(self.m_axi.last, 0)),
        }


@dataclass
class RXFifoCancelTransaction(AbstractValidTransaction):
    cancel_o: Logic = field(default_factory=lambda: Logic("0"))

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except ValueError:
            return default

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(cancel_o=Logic("0"))

    @property
    def valid(self) -> bool:
        return bool(self._to_int(self.cancel_o, 0))

    @valid.setter
    def valid(self, value: bool):
        self.cancel_o = Logic(value)

    @property
    def to_data(self) -> Dict[str, Any]:
        return {"cancel": True}
