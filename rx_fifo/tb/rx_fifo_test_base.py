from cocotb.triggers import RisingEdge, Timer

from rx_fifo.tb.rx_fifo_cancel_monitor import RXFifoCancelMonitor
from rx_fifo.tb.rx_fifo_driver import RXFifoDriver
from rx_fifo.tb.rx_fifo_model import RXFifoModel
from rx_fifo.tb.rx_fifo_monitor import RXFifoAxiStreamMonitor
from rx_fifo.tb.rx_fifo_output_transaction import RXFifoOutputTransaction
from rx_fifo.tb.rx_fifo_ready_driver import RXFifoReadyDriver
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
        monitor=RXFifoAxiStreamMonitor,
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
        self.cancel_monitor = RXFifoCancelMonitor(dut)
        self.cancel_monitor.add_subscriber(self.scoreboard.model, self.driver)
        self.ready_driver = RXFifoReadyDriver(dut, probability=0.7)

    async def wait_for_driver_done(self):
        while await self.driver.busy():
            await RisingEdge(self.dut.s_clk)

        await Timer(1000, unit="ns")
