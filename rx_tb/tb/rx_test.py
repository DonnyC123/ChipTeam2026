import random
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
