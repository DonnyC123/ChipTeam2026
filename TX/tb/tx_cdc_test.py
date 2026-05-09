import cocotb

from TX.tb.tx_cdc_test_base import TxCdcResetTestBase
from TX.tb.tx_test import patterned_frame, queue_id


@cocotb.test()
async def test_split_clock_single_frame(dut):
    tb = await TxCdcResetTestBase.create(dut, dma_clk_period_ns=8, tx_clk_period_ns=10)
    frame = patterned_frame(96, 0x21)

    await tb.run_frames([(frame, 0)], inter_word_gap=1)


@cocotb.test()
async def test_split_clock_back_to_back_frames(dut):
    tb = await TxCdcResetTestBase.create(dut, dma_clk_period_ns=12, tx_clk_period_ns=8)
    frames = [(patterned_frame(64 + idx * 9, 0x40 + idx), 0) for idx in range(6)]

    await tb.run_frames(frames, inter_word_gap=0, post_frame_idle=0, ordered=False)


@cocotb.test()
async def test_reset_recovery_between_packets(dut):
    tb = await TxCdcResetTestBase.create(dut, dma_clk_period_ns=8, tx_clk_period_ns=10)

    await tb.run_frames([(patterned_frame(128, 0x60), 0)], inter_word_gap=1)
    await tb.apply_reset(tx_cycles=7, dma_cycles=5, tx_first=True)
    await tb.run_frames(
        [
            (patterned_frame(80, 0x70), 0),
            (patterned_frame(145, 0x80), queue_id(1)),
        ],
        inter_word_gap=1,
        ordered=False,
    )


@cocotb.test()
async def test_dma_only_reset_recovery(dut):
    tb = await TxCdcResetTestBase.create(dut, dma_clk_period_ns=14, tx_clk_period_ns=10)

    tb.dut.dma_rst.value = 1
    await tb.sequence.add_idle(8)
    tb.dut.dma_rst.value = 0
    await tb.sequence.add_idle(8)

    frames = [(patterned_frame(64 + idx * 5, 0x90 + idx), queue_id(idx)) for idx in range(4)]
    await tb.run_frames(frames, inter_word_gap=1, ordered=False)
