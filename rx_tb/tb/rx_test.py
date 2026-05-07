import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from rx_fifo.tb.rx_fifo_common import initialize_tb, S_CLK_PERIOD_PS, M_CLK_PERIOD_PS

from rx_tb.tb.rx_test_base import RxTestBase


LOCK_IDLES = 64


@cocotb.test()
async def test_lock_and_single_frame(dut):
    await initialize_tb(dut)
    tb = RxTestBase(dut, ready_probability=1.0)

    frame = [0xAA, 0xBB, 0xCC, 0xDD] * 16

    await tb.sequence.send_idles(LOCK_IDLES)
    await tb.sequence.send_ethernet_frame(frame)
    await tb.sequence.send_idles(20)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_back_to_back_frames(dut):
    await initialize_tb(dut)
    tb = RxTestBase(dut, ready_probability=1.0)

    frames = [
        list(range(64)),
        [0xDE, 0xAD, 0xBE, 0xEF] * 18,
        [0xFF] * 128,
    ]

    await tb.sequence.send_idles(LOCK_IDLES)
    await tb.sequence.send_back_to_back_frames(frames, gap_idles=12)
    await tb.sequence.send_idles(20)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_backpressure_drops(dut):
    await initialize_tb(dut)
    tb = RxTestBase(dut, ready_probability=0.3)

    frames = [list(range(8 + i)) for i in range(20)]

    await tb.sequence.send_idles(LOCK_IDLES)
    await tb.sequence.send_back_to_back_frames(frames, gap_idles=4)
    await tb.sequence.send_idles(20)

    await tb.wait_for_driver_done(settle_ns=2000)
    await tb.scoreboard.check()


@cocotb.test()
async def test_long_mixed_traffic(dut, seed: int = 0xC0FFEE):
    await initialize_tb(dut)
    tb = RxTestBase(dut, ready_probability=0.7)
    rng = random.Random(seed)

    NUM_FRAMES = 60

    await tb.sequence.send_idles(LOCK_IDLES)
    for _ in range(NUM_FRAMES):
        size = rng.randint(16, 128)
        frame = [rng.randint(0, 255) for _ in range(size)]
        await tb.sequence.send_ethernet_frame(frame)
        await tb.sequence.send_idles(rng.randint(2, 16))

    await tb.sequence.send_idles(20)
    await tb.wait_for_driver_done(settle_ns=5000)
    await tb.scoreboard.check()


@cocotb.test()
async def test_unreset_pipelines_no_residue(dut):
    """
    The ethernet_assembler instantiates its `out_data_o` and `bytes_valid_o`
    data_pipelines with RST_EN=0 (ethernet_assembler.sv:312, :325). On real
    hardware, those FFs power up to whatever the synthesized primitives
    initialize to — typically 0, but not guaranteed. In sim they default to
    0/X depending on the simulator, masking any vulnerability.

    This test injects a hostile non-zero value into both unreset pipeline
    FFs while reset is held, then releases reset and drives a normal
    IEEE-correct frame (preamble in SOF lanes 1-7, MAC body starting at
    lane 0 of next block — exactly what a QLogic peer transmits). If the
    `out_valid_o` reset gating in rx_fifo_ctrl is sound, the AXI output
    matches the sent frame byte-for-byte. If anything leaks, we'll see a
    residue prefix matching the SOF preamble bytes — the same symptom
    observed on hardware.
    """
    s_clk_gen = Clock(dut.s_clk, S_CLK_PERIOD_PS, unit="ps")
    m_clk_gen = Clock(dut.m_clk, M_CLK_PERIOD_PS, unit="ps")
    cocotb.start_soon(s_clk_gen.start())
    cocotb.start_soon(m_clk_gen.start())

    dut.s_rst.value = 1
    dut.m_rst.value = 1
    dut.raw_valid_i.value = 0
    dut.raw_data_i.value = 0

    for _ in range(4):
        await RisingEdge(dut.s_clk)

    asm = dut.rx_top_inst.u_ethernet_assembler
    bv_ff = asm.data_pipeline_inst7.gen_delay.data_shift_reg_q
    od_ff = asm.data_pipeline_inst6.gen_delay.data_shift_reg_q

    # Hostile preload: bytes_valid = 0xF0 (lanes 4-7 valid), out_data carries
    # the SOF preamble residue pattern observed in the hardware tcpdump.
    # If this leaks, the host stream prefix would be `55 55 55 d5`.
    bv_ff[0].value = 0xF0
    od_ff[0].value = 0xD555_5555_0000_0000

    await RisingEdge(dut.s_clk)
    dut.s_rst.value = 0
    dut.m_rst.value = 0
    await RisingEdge(dut.s_clk)
    await RisingEdge(dut.m_clk)

    tb = RxTestBase(dut, ready_probability=1.0)

    frame = list(range(64))

    await tb.sequence.send_idles(LOCK_IDLES)
    await tb.sequence.send_ethernet_frame(frame)
    await tb.sequence.send_idles(20)

    await tb.wait_for_driver_done()
    await tb.scoreboard.check()


@cocotb.test()
async def test_stress_mixed_traffic(dut, seed: int = 0xDEADBEEF):
    await initialize_tb(dut)
    tb = RxTestBase(dut, ready_probability=0.5)
    rng = random.Random(seed)

    NUM_FRAMES = 1000

    await tb.sequence.send_idles(LOCK_IDLES)
    for _ in range(NUM_FRAMES):
        size = rng.randint(8, 256)
        frame = [rng.randint(0, 255) for _ in range(size)]
        await tb.sequence.send_ethernet_frame(frame)
        await tb.sequence.send_idles(rng.randint(2, 24))

    await tb.sequence.send_idles(40)
    await tb.wait_for_driver_done(settle_ns=10000)
    await tb.scoreboard.check()
