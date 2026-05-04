import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

from tb_utils.generic_test_base import GenericTestBase
from tb_utils.generic_monitor import GenericValidMonitor
from TX.tb.tx_axis_driver import TxAxisDriver
from TX.tb.tx_pcs_transaction import TxPcsTransaction
from TX.tb.tx_scoreboard import Pcs66bChecker, TxScoreboard
from TX.tb.tx_sequence import TxSequence
from TX.tb.tx_sequence_item import TxSequenceItem
from TX.tb.tx_transaction import TxTransaction


CLK_PERIOD_NS = 10
RESET_CYCLES = 5
DRAIN_TIMEOUT_CYCLES = 8000
POST_MATCH_RAW_CHUNKS = 16


class TxFullChainTestBase(GenericTestBase):
    def __init__(
        self,
        dut,
        clk_period_ns: int = CLK_PERIOD_NS,
        reset_cycles: int = RESET_CYCLES,
    ):
        self.dut = dut
        self.clk_period_ns = clk_period_ns
        self.reset_cycles = reset_cycles
        super().__init__(
            dut=dut,
            driver=TxAxisDriver,
            sequence_item=TxSequenceItem,
            sequence=TxSequence,
            monitor=GenericValidMonitor,
            output_transaction=TxTransaction,
            scoreboard=TxScoreboard,
        )
        self.pcs_monitor: GenericValidMonitor | None = None
        self.pcs_checker: Pcs66bChecker | None = None

    @classmethod
    async def create(cls, dut, **kwargs) -> "TxFullChainTestBase":
        tb = cls(dut, **kwargs)
        await tb.initialize()
        return tb

    async def initialize(self):
        cocotb.start_soon(Clock(self.dut.clk, self.clk_period_ns, unit="ns").start())
        self._drive_input_defaults()
        self.dut.rst.value = 1

        self.pcs_monitor = GenericValidMonitor(self.dut, TxPcsTransaction)
        self.pcs_checker = Pcs66bChecker()

        await ClockCycles(self.dut.clk, self.reset_cycles)
        self.dut.rst.value = 0
        await RisingEdge(self.dut.clk)

    def _drive_input_defaults(self):
        self.dut.s_axis_dma_tdata_i.value = 0
        self.dut.s_axis_dma_tkeep_i.value = 0
        self.dut.s_axis_dma_tvalid_i.value = 0
        self.dut.s_axis_dma_tlast_i.value = 0
        self.dut.s_axis_dma_tdest_i.value = 0

    async def send_expected_frame(
        self,
        frame: list[int],
        tdest: int = 0,
        inter_word_gap: int = 0,
        post_frame_idle: int = 0,
    ):
        self.scoreboard.add_expected(frame)
        await self.sequence.send_frame(frame, tdest=tdest, inter_word_gap=inter_word_gap)
        if post_frame_idle:
            await self.sequence.add_idle(post_frame_idle, tdest=tdest)

    async def send_expected_frame_with_gaps(
        self,
        frame: list[int],
        gaps: list[int],
        tdest: int = 0,
        post_frame_idle: int = 0,
    ):
        self.scoreboard.add_expected(frame)
        await self.sequence.send_frame_with_gaps(frame, gaps=gaps, tdest=tdest)
        if post_frame_idle:
            await self.sequence.add_idle(post_frame_idle, tdest=tdest)

    async def run_frames(
        self,
        frames: list[tuple[list[int], int]],
        inter_word_gap: int = 3,
        post_frame_idle: int = 8,
        ordered: bool = True,
        timeout_cycles: int = DRAIN_TIMEOUT_CYCLES,
    ):
        for frame, qid in frames:
            await self.send_expected_frame(
                frame,
                tdest=qid,
                inter_word_gap=inter_word_gap,
                post_frame_idle=post_frame_idle,
            )

        await self.sequence.add_idle(256)
        await self.drain(timeout_cycles=timeout_cycles)
        self.check(ordered=ordered)
        return self.sequence

    async def drain(
        self,
        timeout_cycles: int = DRAIN_TIMEOUT_CYCLES,
        post_match_raw_chunks: int = POST_MATCH_RAW_CHUNKS,
    ):
        raw_after_match = 0
        cycles_after_match = 0

        for _ in range(timeout_cycles):
            while not self.monitor.actual_queue.empty():
                raw = await self.monitor.actual_queue.get()
                self.scoreboard.ingest_raw(int(raw))
                if self.scoreboard.received_expected:
                    raw_after_match += 1

            while not self.pcs_monitor.actual_queue.empty():
                header, payload = await self.pcs_monitor.actual_queue.get()
                self.pcs_checker.ingest(int(header), int(payload))
                self.scoreboard.ingest_pcs(int(header), int(payload))

            if self.scoreboard.received_expected:
                cycles_after_match += 1

            if self.scoreboard.received_expected and (
                raw_after_match >= post_match_raw_chunks
                or cycles_after_match >= post_match_raw_chunks
            ):
                return

            await RisingEdge(self.dut.clk)

        while not self.monitor.actual_queue.empty():
            raw = await self.monitor.actual_queue.get()
            self.scoreboard.ingest_raw(int(raw))

        while not self.pcs_monitor.actual_queue.empty():
            header, payload = await self.pcs_monitor.actual_queue.get()
            self.pcs_checker.ingest(int(header), int(payload))
            self.scoreboard.ingest_pcs(int(header), int(payload))

        self.dut._log.warning(f"Timed out draining TX monitor: {self.scoreboard.summary()}")
        return

    def check(self, ordered: bool = True):
        self.scoreboard.check(ordered=ordered)
        self.pcs_checker.check()
        if self.pcs_checker.error_count:
            raise AssertionError(self.pcs_checker.summary())
        for warning in self.scoreboard.warnings:
            self.dut._log.warning(warning)
        self.dut._log.info(self.scoreboard.summary())
        self.dut._log.info(self.pcs_checker.summary())
