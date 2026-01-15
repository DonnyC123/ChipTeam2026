from cocotb.triggers import Timer, RisingEdge

from tb_utils.generic_drivers import GenericDriver
from tb_utils.generic_sequence import GenericSequence
from tb_utils.generic_monitor import GenericMonitor
from tb_utils.generic_scoreboard import GenericScoreboard
from tb_utils.generic_model import GenericModel
from tb_utils.generic_checker import GenericChecker
from tb_utils.abstract_transactions import AbstractTransaction


class GenericTestBase:
    def __init__(
        self,
        dut,
        driver=GenericDriver,
        sequence_item=AbstractTransaction,
        sequence=GenericSequence,
        monitor=GenericMonitor,
        output_transaction=AbstractTransaction,
        scoreboard=GenericScoreboard,
        model=GenericModel,
        checker=GenericChecker,
    ):
        self.dut = dut
        self.driver = driver(dut=dut, seq_item_type=sequence_item)
        self.sequence = sequence(driver=self.driver)
        self.monitor = monitor(dut=dut, output_transaction=output_transaction)
        self.scoreboard = scoreboard(
            monitor=self.monitor, model=model(), checker=checker()
        )

    async def wait_for_driver_done(self):
        while await self.driver.busy():
            await RisingEdge(self.dut.clk)

        # This is a very dumb way of doing this
        await Timer(1000, unit="ns")

