from typing import Any, Type

from cocotb.triggers import ReadOnly, RisingEdge
from cocotb.types import Logic

from ethernet_parser.tb.ethernet_parser_transaction import EthernetParserTransaction
from tb_utils.generic_monitor import GenericMonitor


class EthernetParserMonitor(GenericMonitor[EthernetParserTransaction]):
    def __init__(
        self,
        dut,
        output_transaction: Type[EthernetParserTransaction],
        clk=None,
    ):
        self._previous_payload_time_o = 0
        super().__init__(dut=dut, output_transaction=output_transaction, clk=clk)

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    async def receive_transaction(self) -> EthernetParserTransaction:
        while True:
            await RisingEdge(self._clk)
            await ReadOnly()

            current_payload_time = self._to_int(self.dut.payload_time_o.value, 0)
            output_transaction = self.output_transaction()

            if self._to_int(self.dut.valid_o.value, 0):
                output_transaction.valid_o = Logic(1)
                output_transaction.outputs_o = self.dut.outputs_o.value
                output_transaction.payload_time_o = Logic(
                    self._previous_payload_time_o
                )
                self._previous_payload_time_o = current_payload_time
                return output_transaction

            self._previous_payload_time_o = current_payload_time
