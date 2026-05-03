from typing import TypeVar

from tb_utils.abstract_transactions import AbstractTransaction
from tb_utils.generic_drivers import GenericDriver

GenericSequenceItem = TypeVar("GenericSequenceItem", bound=AbstractTransaction)


class RxDriver(GenericDriver[GenericSequenceItem]):
    def __init__(self, dut, seq_item_type: GenericSequenceItem):
        super().__init__(dut, seq_item_type, clk=dut.s_clk)
