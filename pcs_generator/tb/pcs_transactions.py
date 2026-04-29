from dataclasses import dataclass, field
from typing import Any, ClassVar, Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractValidTransaction


@dataclass
class PCSOutputBlockTransaction(AbstractValidTransaction):
    DATA_W: ClassVar[int] = 64
    CONTROL_W: ClassVar[int] = 2
    NUM_BYTES: ClassVar[int] = DATA_W // 8

    out_data_o: LogicArray = field(
        default_factory=lambda: LogicArray("0" * PCSOutputBlockTransaction.DATA_W)
    )
    out_control_o: LogicArray = field(
        default_factory=lambda: LogicArray("0" * PCSOutputBlockTransaction.CONTROL_W)
    )
    out_valid_o: Logic = field(default_factory=lambda: Logic("0"))

    def __post_init__(self):
        self.out_data_o = self._coerce_logic_array(self.out_data_o, self.DATA_W)
        self.out_control_o = self._coerce_logic_array(
            self.out_control_o, self.CONTROL_W
        )
        self.out_valid_o = self._coerce_logic(self.out_valid_o)

    @staticmethod
    def _coerce_logic(value: Any, default: str = "0") -> Logic:
        if value is None:
            return Logic(default)
        if isinstance(value, Logic):
            return value
        return Logic(value)

    @staticmethod
    def _coerce_logic_array(
        value: Any, width: int, default_fill: str = "0"
    ) -> LogicArray:
        if value is None:
            return LogicArray(default_fill * width)
        if isinstance(value, LogicArray):
            return value
        if isinstance(value, int):
            return LogicArray(format(value, f"0{width}b"))
        return LogicArray(value)

    @classmethod
    def invalid_seq_item(cls) -> Self:
        return cls(out_data_o=0, out_control_o=0, out_valid_o=0)

    @property
    def valid(self) -> bool:
        return bool(self.out_valid_o)

    @valid.setter
    def valid(self, value: bool):
        self.out_valid_o = self._coerce_logic(value)

    @property
    def to_data(self) -> Any:
        return (int(self.out_control_o), int(self.out_data_o), bool(self.out_valid_o))
