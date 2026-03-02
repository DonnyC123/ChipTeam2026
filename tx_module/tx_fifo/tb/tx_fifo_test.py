import cocotb
from cocotb.triggers import RisingEdge, Timer

from tx_fifo.tb.tx_fifo_test_base import TxFifoTestBase
from tb_utils.tb_common import initialize_tb


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
    """Burst-write 8 words (half of DEPTH=16), then read all 32 beats."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxFifoTestBase(dut)

    words = [0x_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000 + i
             for i in range(8)]
    await testbase.sequence.add_burst_write_then_read(words)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()
