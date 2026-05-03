import cocotb

from rx_fifo.tb.rx_fifo_common import initialize_tb

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
    """Stress test with frequent backpressure to exercise FIFO drops.
    Checker performs in-order subset matching, so missing packets are
    tolerated as long as the received packets match expected packets in order."""
    await initialize_tb(dut)
    tb = RxTestBase(dut, ready_probability=0.3)

    frames = [list(range(8 + i)) for i in range(20)]

    await tb.sequence.send_idles(LOCK_IDLES)
    await tb.sequence.send_back_to_back_frames(frames, gap_idles=4)
    await tb.sequence.send_idles(20)

    await tb.wait_for_driver_done(settle_ns=5000)
    await tb.scoreboard.check()
