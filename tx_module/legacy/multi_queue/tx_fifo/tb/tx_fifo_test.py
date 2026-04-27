import random

import cocotb
from cocotb.triggers import RisingEdge

from tb_utils.tb_common import initialize_tb
from tx_fifo_test_base import TxFifoTestBase


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

    for i in range(num_words):
        data = rng.getrandbits(256)
        valid_mask = rng.getrandbits(32)
        # Random packet boundaries: only the last word of a random packet has last=1.
        last = 1 if (i % rng.randint(3, 9) == 0) else 0
        await testbase.sequence.add_write(data=data, valid_mask=valid_mask, last=last)

    for _ in range(num_words * 4):
        await testbase.sequence.add_read()

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_fifo_random_rw_jitter_keep_last_long_test(dut):
    """Stress: random read jitter + random tkeep/tlast over long mixed traffic."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxFifoTestBase(dut)

    rng = random.Random(0xF17E_2026)
    depth = _get_depth(dut)

    # Build long randomized packetized stream.
    total_words = depth * 10
    words = []
    remaining = total_words
    while remaining > 0:
        pkt_len = min(remaining, rng.randint(1, 7))
        for idx in range(pkt_len):
            words.append(
                (
                    rng.getrandbits(256),
                    rng.getrandbits(32),
                    1 if idx == (pkt_len - 1) else 0,
                )
            )
        remaining -= pkt_len

    write_idx = 0
    phase_cycles = total_words * 12
    for _ in range(phase_cycles):
        do_write = (write_idx < total_words) and (rng.random() < 0.55)
        do_read = rng.random() < 0.65

        if do_write:
            data, keep, last = words[write_idx]
            write_idx += 1
        else:
            data, keep, last = 0, 0, 0

        await testbase.sequence.add_cycle(
            write_en=do_write,
            data=data,
            valid_mask=keep,
            last=last,
            read_en=do_read,
            sched_req=do_write,
        )

        if write_idx >= total_words and rng.random() < 0.90:
            break

    # Drain phase.
    for _ in range(total_words * 8):
        await testbase.sequence.add_cycle(write_en=False, read_en=True, sched_req=False)

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
    """Read while empty should keep valid mask at zero (sequence-driven)."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxFifoTestBase(dut)

    await testbase.sequence.add_read()
    await RisingEdge(dut.clk)

    assert int(dut.empty_o.value) == 1, "FIFO should stay empty"
    assert int(dut.pcs_valid_o.value) == 0, "pcs_valid_o must be 0 when FIFO is empty"

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_fifo_overflow_flag_test(dut):
    """Write while full should raise overflow_o (sequence-driven)."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxFifoTestBase(dut)

    depth = _get_depth(dut)
    overflow_seen = False

    for i in range(depth):
        await testbase.sequence.add_cycle(
            write_en=True,
            data=i,
            valid_mask=0xFFFF_FFFF,
            last=0,
            read_en=False,
            sched_req=True,
        )
        await RisingEdge(dut.clk)
        overflow_seen = overflow_seen or bool(int(dut.overflow_o.value))

    await testbase.sequence.add_cycle(
        write_en=True,
        data=0xDEAD_BEEF,
        valid_mask=0xFFFF_FFFF,
        last=0,
        read_en=False,
        sched_req=True,
    )
    await RisingEdge(dut.clk)
    overflow_seen = overflow_seen or bool(int(dut.overflow_o.value))

    assert int(dut.full_o.value) == 1, "FIFO should be full"
    assert overflow_seen, "overflow_o should assert on write-while-full"

    await testbase.sequence.add_idle()
    await RisingEdge(dut.clk)
    assert int(dut.overflow_o.value) == 0, "overflow_o should deassert when not overflowing"

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()
