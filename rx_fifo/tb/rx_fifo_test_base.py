from cocotb.triggers import RisingEdge, Timer

from rx_fifo.tb.rx_fifo_driver import RXFifoDriver
from rx_fifo.tb.rx_fifo_model import RXFifoModel
from rx_fifo.tb.rx_fifo_monitor import GenericValidMonitor
from rx_fifo.tb.rx_fifo_output_transaction import RXFifoOutputTransaction
from rx_fifo.tb.rx_fifo_sequence import RXFifoSequence
from rx_fifo.tb.rx_fifo_sequence_item import RXFifoSequenceItem
from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_scoreboard import GenericScoreboard
from tb_utils.generic_test_base import GenericTestBase


class RXFifoTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        driver=RXFifoDriver,
        sequence_item=RXFifoSequenceItem,
        sequence=RXFifoSequence,
        monitor=GenericValidMonitor,
        output_transaction=RXFifoOutputTransaction,
        scoreboard=GenericScoreboard,
        model=RXFifoModel,
        checker=GenericChecker,
    ):
        super().__init__(
            dut,
            driver,
            sequence_item,
            sequence,
            monitor,
            output_transaction,
            scoreboard,
            model,
            checker,
        )
        self.sequence.add_subscriber(self.scoreboard)

    async def wait_for_driver_done(self):
        while await self.driver.busy():
            await RisingEdge(self.dut.s_clk)

        await Timer(1000, unit="ns")
