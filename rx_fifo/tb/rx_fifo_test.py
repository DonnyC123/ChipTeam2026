import random

import cocotb

from rx_fifo.tb.rx_fifo_common import initialize_tb
from rx_fifo.tb.rx_fifo_test_base import RXFifoTestBase


@cocotb.test()
async def run_basic_random_packet_test(dut, seed: int | None = 596):
    await initialize_tb(dut)
    testbase = RXFifoTestBase(dut)
    rng = random.Random(seed)

    await testbase.sequence.add_valid_random_input(rng=rng, mask_toggle=1)

    for _ in range(10):
        await testbase.sequence.add_valid_random_input(rng=rng, mask_toggle=0)

    await testbase.sequence.add_random_last_in(rng=rng, mask_toggle=1)
    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()
