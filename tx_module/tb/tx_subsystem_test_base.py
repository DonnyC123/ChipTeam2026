from cocotb import start_soon
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_monitor import GenericValidMonitor
from tb_utils.generic_scoreboard import GenericScoreboard
from tb_utils.generic_test_base import GenericTestBase
from tx_axis_driver import TxAxisDriver
from tx_subsystem_model import TxSubsystemModel
from tx_subsystem_out_transaction import TxSubsystemOutTransaction
from tx_subsystem_sequence import TxSubsystemSequence
from tx_subsystem_sequence_item import TxSubsystemSequenceItem


class TxSubsystemTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        dma_period_ns=8,
        tx_period_ns=10,
        driver=TxAxisDriver,
        sequence_item=TxSubsystemSequenceItem,
        sequence=TxSubsystemSequence,
        monitor=GenericValidMonitor,
        output_transaction=TxSubsystemOutTransaction,
        scoreboard=GenericScoreboard,
        model=TxSubsystemModel,
        checker=GenericChecker,
    ):
        self.dma_period_ns = dma_period_ns
        self.tx_period_ns = tx_period_ns
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

    async def start_clocks_and_reset(self):
        self.dut.s_axis_dma_tdata_i.value = 0
        self.dut.s_axis_dma_tkeep_i.value = 0
        self.dut.s_axis_dma_tvalid_i.value = 0
        self.dut.s_axis_dma_tlast_i.value = 0
        self.dut.m_axis_pcs_tready_i.value = 1
        self.dut.dma_aresetn.value = 0
        self.dut.tx_aresetn.value = 0

        start_soon(Clock(self.dut.dma_aclk, self.dma_period_ns, unit="ns").start())
        start_soon(Clock(self.dut.tx_aclk, self.tx_period_ns, unit="ns").start())

        await Timer(max(self.dma_period_ns, self.tx_period_ns) * 4, unit="ns")
        await RisingEdge(self.dut.dma_aclk)
        await RisingEdge(self.dut.tx_aclk)
        self.dut.dma_aresetn.value = 1
        self.dut.tx_aresetn.value = 1

        for _ in range(4):
            await RisingEdge(self.dut.tx_aclk)

    async def reset(self):
        self.dut.dma_aresetn.value = 0
        self.dut.tx_aresetn.value = 0
        self.dut.s_axis_dma_tvalid_i.value = 0
        self.dut.m_axis_pcs_tready_i.value = 1
        for _ in range(4):
            await RisingEdge(self.dut.tx_aclk)
        self.dut.dma_aresetn.value = 1
        self.dut.tx_aresetn.value = 1
        for _ in range(4):
            await RisingEdge(self.dut.tx_aclk)

    async def set_pcs_ready(self, ready: int):
        await RisingEdge(self.dut.tx_aclk)
        self.dut.m_axis_pcs_tready_i.value = 1 if ready else 0

    async def wait_for_expected_outputs(self, timeout_cycles=10000):
        target = self.scoreboard.model.expected_queue.qsize()
        for _ in range(timeout_cycles):
            if self.monitor.actual_queue.qsize() >= target:
                return
            await RisingEdge(self.dut.tx_aclk)
        raise AssertionError(
            f"Timed out waiting for output beats: "
            f"expected={target} actual={self.monitor.actual_queue.qsize()}"
        )

    async def drain_and_check(self, timeout_cycles=10000):
        await self.driver.wait_until_idle()
        await self.wait_for_expected_outputs(timeout_cycles=timeout_cycles)
        for _ in range(8):
            await RisingEdge(self.dut.tx_aclk)
        await self.scoreboard.check()
