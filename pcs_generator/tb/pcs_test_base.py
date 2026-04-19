from typing import Any, Optional, Type

from cocotb.triggers import RisingEdge, Timer

from pcs_generator.tb.pcs_drivers import PCSDriver
from pcs_generator.tb.pcs_model import GenericModel as PCSModel
from pcs_generator.tb.pcs_monitor import PCSMonitor
from pcs_generator.tb.pcs_sequence import PCSSequence
from pcs_generator.tb.pcs_sequence_item import PCSSequenceItem
from pcs_generator.tb.pcs_transactions import PCSOutputBlockTransaction
from tb_utils.abstract_transactions import AbstractTransaction


class PCSTestBase:
    def __init__(
        self,
        dut,
        driver: Type[PCSDriver] = PCSDriver,
        sequence_item: Type[PCSSequenceItem] = PCSSequenceItem,
        sequence: Type[PCSSequence] = PCSSequence,
        monitor: Optional[Type[Any]] = PCSMonitor,
        output_transaction: Optional[Type[AbstractTransaction]] = PCSOutputBlockTransaction,
        scoreboard: Optional[Type[Any]] = None,
        model: Type[PCSModel] = PCSModel,
        checker: Optional[Type[Any]] = None,
    ):
        self.dut = dut

        self.driver = driver(dut=dut, seq_item_type=sequence_item)
        self.sequence = sequence(driver=self.driver)
        self.model = model()

        self.monitor = None
        self.checker = None
        self.scoreboard = None

        if monitor is not None:
            self.monitor = monitor(dut=dut, output_transaction=output_transaction)

        if checker is not None:
            self.checker = checker()

        if scoreboard is not None:
            if self.monitor is None:
                raise ValueError(
                    "monitor and output_transaction must be provided when constructing a scoreboard"
                )
            if self.checker is None:
                raise ValueError("checker must be provided when constructing a scoreboard")

            self.scoreboard = scoreboard(
                monitor=self.monitor, model=self.model, checker=self.checker
            )
            self.sequence.add_subscriber(self.scoreboard)

    async def wait_for_driver_done(self):
        while await self.driver.busy():
            await RisingEdge(self.dut.clk)

        await Timer(1000, unit="ns")

    async def check_outputs(self):
        if self.scoreboard is None:
            raise RuntimeError("scoreboard must be configured before checking outputs")

        self.model.assert_complete()
        if self.monitor is not None:
            self.monitor.assert_complete()

        await self.scoreboard.check()


GenericTestBase = PCSTestBase
