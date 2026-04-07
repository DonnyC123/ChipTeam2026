import cocotb
import random
from cocotb.triggers import RisingEdge, Timer

from tx_fifo.tb.tx_fifo_test_base import TxFifoTestBase
from tb_utils.tb_common import initialize_tb


def _get_depth(dut, default=64) -> int:
    if hasattr(dut, "DEPTH"):
        try:
            return int(dut.DEPTH.value)
        except Exception:
            pass
    return default


@cocotb.test()
async def tx_fifo_single_word_test(dut):
    """Write one 256-bit word, read 4 x 64-bit beats, verify width conversion."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxFifoTestBase(dut)

    await testbase.sequence.add_write_and_readout(
        data=0x_DDDD_DDDD_CCCC_CCCC_BBBB_BBBB_AAAA_AAAA_9999_9999_8888_8888_7777_7777_6666_6666,
        valid_mask=0xFFFF_FFFF,
    )

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_fifo_multi_word_test(dut):
    """Write 3 words back-to-back, then read all 12 beats."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxFifoTestBase(dut)

    words = [
        0x_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111,
        0x_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222,
        0x_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333,
    ]
    await testbase.sequence.add_burst_write_then_read(words)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_fifo_partial_valid_test(dut):
    """Write with partial valid mask, verify only corresponding bytes are valid."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxFifoTestBase(dut)

    await testbase.sequence.add_write_and_readout(
        data=0x_FF00_FF00_FF00_FF00_FF00_FF00_FF00_FF00_FF00_FF00_FF00_FF00_FF00_FF00_FF00_FF00,
        valid_mask=0x0F0F_0F0F,
    )

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_fifo_interleaved_test(dut):
    """Write word, read 4 beats, write another word, read 4 beats."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxFifoTestBase(dut)

    await testbase.sequence.add_write_and_readout(
        data=0x_AAAA_AAAA_AAAA_AAAA_AAAA_AAAA_AAAA_AAAA_AAAA_AAAA_AAAA_AAAA_AAAA_AAAA_AAAA_AAAA,
    )
    await testbase.sequence.add_write_and_readout(
        data=0x_BBBB_BBBB_BBBB_BBBB_BBBB_BBBB_BBBB_BBBB_BBBB_BBBB_BBBB_BBBB_BBBB_BBBB_BBBB_BBBB,
    )

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_fifo_burst_depth_test(dut):
    """Burst-write 8 words, then read all 32 beats."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxFifoTestBase(dut)

    words = [
        0x_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000
        + i
        for i in range(8)
    ]
    await testbase.sequence.add_burst_write_then_read(words)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_fifo_long_random_values_test(dut):
    """Long randomized stream with random data and valid masks."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxFifoTestBase(dut)

    rng = random.Random(0xF1F0_2026)
    depth = _get_depth(dut)
    num_words = depth * 3

    for _ in range(num_words):
        data = rng.getrandbits(256)
        valid_mask = rng.getrandbits(32)
        await testbase.sequence.add_write(data=data, valid_mask=valid_mask)

    for _ in range(num_words * 4):
        await testbase.sequence.add_read()

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_fifo_write_when_full_drop_test(dut):
    """Write DEPTH+1 words without reads; the extra write should be dropped."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxFifoTestBase(dut)

    depth = _get_depth(dut)

    words = [
        0x_1000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000
        + i
        for i in range(depth + 1)
    ]
    await testbase.sequence.add_burst_write_then_read(words)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_fifo_empty_read_outputs_zero_valid_test(dut):
    """Read while empty should keep valid mask at zero."""
    await initialize_tb(dut, clk_period_ns=10)

    dut.dma_data_i.value = 0
    dut.dma_valid_i.value = 0
    dut.dma_last_i.value = 0
    dut.dma_wr_en_i.value = 0
    dut.sched_req_i.value = 0
    dut.pcs_read_i.value = 1

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    assert int(dut.empty_o.value) == 1, "FIFO should stay empty"
    assert int(dut.pcs_valid_o.value) == 0, "pcs_valid_o must be 0 when FIFO is empty"


@cocotb.test()
async def tx_fifo_overflow_flag_test(dut):
    """Write while full should raise overflow_o."""
    await initialize_tb(dut, clk_period_ns=10)

    depth = _get_depth(dut)

    dut.pcs_read_i.value = 0
    dut.sched_req_i.value = 1
    dut.dma_valid_i.value = 0xFFFF_FFFF
    dut.dma_last_i.value = 0

    # Fill the FIFO.
    for i in range(depth):
        dut.dma_data_i.value = i
        dut.dma_wr_en_i.value = 1
        await RisingEdge(dut.clk)

    # One extra write should trigger overflow.
    dut.dma_data_i.value = 0xDEAD_BEEF
    dut.dma_wr_en_i.value = 1
    await RisingEdge(dut.clk)
    assert int(dut.full_o.value) == 1, "FIFO should be full"
    assert int(dut.overflow_o.value) == 1, "overflow_o should assert on write-while-full"

    # Stop writing; overflow flag should drop.
    dut.dma_wr_en_i.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.overflow_o.value) == 0, "overflow_o should deassert when not overflowing"
