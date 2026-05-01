from dataclasses import dataclass, field
from typing import Any, Dict, Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class RXFifoSequenceItem(AbstractTransaction):
    DATA_IN_W = 64
    IN_MASK_W = 8
    OUT_MASK_W = 32
    DATA_OUT_W = 256

    # Signals driven by the input-side driver. m_axi.ready is owned by the
    # consumer-side ready driver, so it is intentionally NOT here.
    data_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * RXFifoSequenceItem.DATA_IN_W)
    )
    mask_i: LogicArray = field(
        default_factory=lambda: LogicArray("X" * RXFifoSequenceItem.IN_MASK_W)
    )
    valid_i: Logic = field(default_factory=lambda: Logic("0"))
    rst: Logic = field(default_factory=lambda: Logic("0"))

    drop_i: Logic = field(default_factory=lambda: Logic("0"))
    send_i: Logic = field(default_factory=lambda: Logic("0"))

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except ValueError:
            return default

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(
            data_i=LogicArray("X" * cls.DATA_IN_W),
            mask_i=LogicArray("X" * cls.IN_MASK_W),
            rst=Logic(0),
            valid_i=Logic(0),
            drop_i=Logic(0),
            send_i=Logic(0),
        )

    @property
    def valid(self) -> bool:
        return bool(self._to_int(self.valid_i, 0))

    @valid.setter
    def valid(self, value: bool):
        self.valid_i = Logic(value)

    @property
    def to_data(self) -> Dict[str, Any]:
        return {
            "rst": bool(self._to_int(self.rst, 0)),
            "data_i": self._to_int(self.data_i, 0),
            "mask_i": self._to_int(self.mask_i, 0),
            "valid_i": bool(self._to_int(self.valid_i, 0)),
            "drop_i": bool(self._to_int(self.drop_i, 0)),
            "send_i": bool(self._to_int(self.send_i, 0)),
        }
