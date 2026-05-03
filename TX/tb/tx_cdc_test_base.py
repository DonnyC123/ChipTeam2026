import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

from tb_utils.generic_monitor import GenericValidMonitor
from TX.tb.tx_pcs_transaction import TxPcsTransaction
from TX.tb.tx_scoreboard import Pcs66bChecker, TxScoreboard
from TX.tb.tx_test_base import RESET_CYCLES, TxFullChainTestBase


class TxCdcResetTestBase(TxFullChainTestBase):
    def __init__(
        self,
        dut,
        tx_clk_period_ns: int = 10,
        dma_clk_period_ns: int = 8,
        reset_cycles: int = RESET_CYCLES,
    ):
        self.tx_clk_period_ns = tx_clk_period_ns
        self.dma_clk_period_ns = dma_clk_period_ns
        super().__init__(
            dut=dut,
            clk_period_ns=tx_clk_period_ns,
            reset_cycles=reset_cycles,
        )

    @classmethod
    async def create(cls, dut, **kwargs) -> "TxCdcResetTestBase":
        tb = cls(dut, **kwargs)
        await tb.initialize()
        return tb

    async def initialize(self):
        cocotb.start_soon(Clock(self.dut.clk, self.tx_clk_period_ns, unit="ns").start())
        cocotb.start_soon(
            Clock(self.dut.dma_clk, self.dma_clk_period_ns, unit="ns").start()
        )
        self._drive_input_defaults()
        self.dut.rst.value = 1
        self.dut.dma_rst.value = 1
        self.pcs_monitor = GenericValidMonitor(self.dut, TxPcsTransaction)
        self.pcs_checker = Pcs66bChecker()

        await ClockCycles(self.dut.clk, self.reset_cycles)
        await ClockCycles(self.dut.dma_clk, self.reset_cycles)
        self.dut.dma_rst.value = 0
        await ClockCycles(self.dut.dma_clk, 2)
        self.dut.rst.value = 0
        await RisingEdge(self.dut.clk)

    async def apply_reset(
        self,
        tx_cycles: int = RESET_CYCLES,
        dma_cycles: int = RESET_CYCLES,
        tx_first: bool = False,
    ):
        self._drive_input_defaults()
        if tx_first:
            self.dut.rst.value = 1
            await ClockCycles(self.dut.clk, 1)
            self.dut.dma_rst.value = 1
        else:
            self.dut.dma_rst.value = 1
            await ClockCycles(self.dut.dma_clk, 1)
            self.dut.rst.value = 1

        await ClockCycles(self.dut.dma_clk, dma_cycles)
        await ClockCycles(self.dut.clk, tx_cycles)
        self.reset_observers()
        self.dut.dma_rst.value = 0
        await ClockCycles(self.dut.dma_clk, 2)
        self.dut.rst.value = 0
        await ClockCycles(self.dut.clk, 4)

    def reset_observers(self):
        self.scoreboard = TxScoreboard(monitor=self.monitor)
        self.pcs_checker = Pcs66bChecker()
        self._flush_monitor_queue(self.monitor.actual_queue)
        self._flush_monitor_queue(self.pcs_monitor.actual_queue)

    @staticmethod
    def _flush_monitor_queue(queue):
        while not queue.empty():
            queue.get_nowait()
