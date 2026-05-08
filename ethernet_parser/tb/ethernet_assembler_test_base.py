from cocotb.triggers import RisingEdge, Timer

from rx_fifo.tb.rx_fifo_output_transaction import RXFifoOutputTransaction
from rx_fifo.tb.rx_fifo_ready_driver import RXFifoReadyDriver
from tb_utils.generic_test_base import GenericTestBase

from rx_tb.tb.rx_checker import RxChecker
from rx_tb.tb.rx_driver import RxDriver
from rx_tb.tb.rx_event_monitor import RxEventMonitor
from rx_tb.tb.rx_model import RxModel
from rx_tb.tb.rx_sequence import RxSequence
from rx_tb.tb.rx_sequence_item import RxSequenceItem


class RxTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        ready_probability: float = 0.7,
        driver=RxDriver,
        sequence_item=RxSequenceItem,
        sequence=RxSequence,
        monitor=RxEventMonitor,
        output_transaction=RXFifoOutputTransaction,
        model=RxModel,
        checker=RxChecker,
    ):
        super().__init__(
            dut,
            driver=driver,
            sequence_item=sequence_item,
            sequence=sequence,
            monitor=monitor,
            output_transaction=output_transaction,
            model=model,
            checker=checker,
        )
        self.sequence.add_subscriber(self.scoreboard)
        self.ready_driver = RXFifoReadyDriver(dut, probability=ready_probability)

    async def wait_for_driver_done(self, settle_ns: float = 1000):
        while await self.driver.busy():
            await RisingEdge(self.dut.s_clk)
        await Timer(settle_ns, unit="ns")
