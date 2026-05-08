from cocotb.triggers import RisingEdge, Timer

from ethernet_parser.tb.ethernet_parser_driver import EthernetParserDriver
from ethernet_parser.tb.ethernet_parser_transaction import (
    EthernetParserTransaction,
)
from ethernet_parser.tb.ethernet_parser_model import EthernetParserModel
from ethernet_parser.tb.ethernet_parser_sequence_item import (
    EthernetParserSequenceItem,
)
from ethernet_parser.tb.ethernet_sequencer import EthernetParserSequence
from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard


class EthernetParserTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        driver=EthernetParserDriver,
        sequence_item=EthernetParserSequenceItem,
        sequence=EthernetParserSequence,
        monitor=GenericValidMonitor,
        output_transaction=EthernetParserTransaction,
        scoreboard=GenericScoreboard,
        model=EthernetParserModel,
        checker=GenericChecker,
    ):
        super().__init__(
            dut,
            driver=driver,
            sequence_item=sequence_item,
            sequence=sequence,
            monitor=monitor,
            output_transaction=output_transaction,
            scoreboard=scoreboard,
            model=model,
            checker=checker,
        )
        self.sequence.add_subscriber(self.scoreboard)

    async def wait_for_driver_done(self, settle_ns: float = 1000):
        while await self.driver.busy():
            await RisingEdge(self.dut.clk)
        await Timer(settle_ns, unit="ns")
