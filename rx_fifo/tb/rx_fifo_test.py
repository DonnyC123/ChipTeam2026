import random

import cocotb

from rx_fifo.tb.rx_fifo_common import initialize_tb
from rx_fifo.tb.rx_fifo_test_base import RXFifoTestBase


@cocotb.test()
async def run_basic_random_packet_test(dut, seed: int | None = 596):
    await initialize_tb(dut)
    testbase = RXFifoTestBase(dut)
    rng = random.Random(seed)

    await testbase.sequence.generate_random_valid_packet(rng=rng)
    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def run_random_packet_stream_test(dut, seed: int | None = 4242):
    await initialize_tb(dut)
    testbase = RXFifoTestBase(dut)
    rng = random.Random(seed)
    seq = testbase.sequence

    NUM_PACKETS = 25
    for _ in range(NUM_PACKETS):
        await seq.generate_random_valid_packet(rng=rng)
        await seq.apply_inter_packet_gap(rng=rng)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()
