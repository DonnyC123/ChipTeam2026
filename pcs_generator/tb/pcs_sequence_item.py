from dataclasses import InitVar, dataclass, field
from typing import Any, ClassVar, Self

from cocotb.types import Logic, LogicArray

from tb_utils.abstract_transactions import AbstractTransaction


@dataclass
class TxAxisSlaveTransaction:
    TDATA_W: ClassVar[int] = 64
    TKEEP_W: ClassVar[int] = TDATA_W // 8

    tdata: LogicArray = field(
        default_factory=lambda: LogicArray("X" * TxAxisSlaveTransaction.TDATA_W)
    )
    tkeep: LogicArray = field(
        default_factory=lambda: LogicArray("0" * TxAxisSlaveTransaction.TKEEP_W)
    )
    tvalid: Logic = field(default_factory=lambda: Logic("0"))
    tlast: Logic = field(default_factory=lambda: Logic("0"))


@dataclass
class PCSSequenceItem(AbstractTransaction):
    TDATA_W: ClassVar[int] = 64
    TKEEP_W: ClassVar[int] = 8
    BLOCK_TYPE_W: ClassVar[int] = 8

    axis_slave_if: TxAxisSlaveTransaction = field(default_factory=TxAxisSlaveTransaction)
    out_ready_i: Logic = field(default_factory=lambda: Logic("1"))
    block_type: InitVar[Any] = None
    tready: InitVar[Any] = None

    def __post_init__(self, block_type: Any, tready: Any):
        self._block_type = self._coerce_logic_array(
            block_type, self.BLOCK_TYPE_W, default_fill="0"
        )
        self._tready = self._coerce_logic(tready, default="0")

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
        return cls(
            axis_slave_if=TxAxisSlaveTransaction(
                tdata=LogicArray("X" * cls.TDATA_W),
                tkeep=LogicArray("0" * cls.TKEEP_W),
                tvalid=Logic("0"),
                tlast=Logic("0"),
            ),
            out_ready_i=Logic("1"),
            block_type=LogicArray("0" * cls.BLOCK_TYPE_W),
            tready=Logic("0"),
        )

    @property
    def valid(self) -> bool:
        return bool(self.axis_slave_if.tvalid)

    @valid.setter
    def valid(self, value: bool):
        self.axis_slave_if.tvalid = Logic(value)

    @property
    def to_data(self) -> int:
        return self.block_type.integer

    @property
    def tdata(self) -> LogicArray:
        return self.axis_slave_if.tdata

    @tdata.setter
    def tdata(self, value: Any):
        self.axis_slave_if.tdata = self._coerce_logic_array(
            value, self.TDATA_W, default_fill="X"
        )

    @property
    def tkeep(self) -> LogicArray:
        return self.axis_slave_if.tkeep

    @tkeep.setter
    def tkeep(self, value: Any):
        self.axis_slave_if.tkeep = self._coerce_logic_array(
            value, self.TKEEP_W, default_fill="0"
        )

    @property
    def tvalid(self) -> Logic:
        return self.axis_slave_if.tvalid

    @tvalid.setter
    def tvalid(self, value: Any):
        self.axis_slave_if.tvalid = self._coerce_logic(value, default="0")

    @property
    def tlast(self) -> Logic:
        return self.axis_slave_if.tlast

    @tlast.setter
    def tlast(self, value: Any):
        self.axis_slave_if.tlast = self._coerce_logic(value, default="0")

    @property
    def out_ready(self) -> Logic:
        return self.out_ready_i

    @out_ready.setter
    def out_ready(self, value: Any):
        self.out_ready_i = self._coerce_logic(value, default="1")


def _get_block_type(self: PCSSequenceItem) -> LogicArray:
    return self._block_type


def _set_block_type(self: PCSSequenceItem, value: Any):
    self._block_type = self._coerce_logic_array(
        value, self.BLOCK_TYPE_W, default_fill="0"
    )


def _get_tready(self: PCSSequenceItem) -> Logic:
    return self._tready


def _set_tready(self: PCSSequenceItem, value: Any):
    self._tready = self._coerce_logic(value, default="0")


PCSSequenceItem.block_type = property(_get_block_type, _set_block_type)
PCSSequenceItem.tready = property(_get_tready, _set_tready)
