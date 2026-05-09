import os
import random

import cocotb
from cocotb.triggers import RisingEdge

from tx_subsystem_test_base import TxSubsystemTestBase


DMA_KEEP_ALL = 0xFFFF_FFFF


def _tail_keep(num_bytes: int) -> int:
    return (1 << num_bytes) - 1


async def _new_testbase(dut, dma_period_ns=8, tx_period_ns=10):
    testbase = TxSubsystemTestBase(
        dut,
        dma_period_ns=dma_period_ns,
        tx_period_ns=tx_period_ns,
    )
    await testbase.start_clocks_and_reset()
    return testbase


@cocotb.test()
async def test_single_word_packet(dut):
    testbase = await _new_testbase(dut)

    await testbase.sequence.add_dma_axis_word(
        data=0x1122_3344_5566_7788_99AA_BBCC_DDEE_FF00_0123_4567_89AB_CDEF_FEDC_BA98_7654_3210,
        keep=DMA_KEEP_ALL,
        last=1,
    )

    await testbase.drain_and_check()


@cocotb.test()
async def test_multi_word_packet(dut):
    testbase = await _new_testbase(dut)

    for idx in range(4):
        await testbase.sequence.add_dma_axis_word(
            data=(0x1000 << 240) | idx,
            keep=(0x0000_0FFF if idx == 3 else DMA_KEEP_ALL),
            last=(idx == 3),
        )

    await testbase.drain_and_check()


@cocotb.test()
async def test_all_tail_keep_lengths(dut):
    testbase = await _new_testbase(dut)

    for keep_bytes in range(1, 33):
        data = (keep_bytes << 248) | random.Random(keep_bytes).getrandbits(248)
        await testbase.sequence.add_dma_axis_word(
            data=data,
            keep=_tail_keep(keep_bytes),
            last=1,
        )
        await testbase.sequence.add_idle(1)

    await testbase.drain_and_check(timeout_cycles=16000)


@cocotb.test()
async def test_dma_backpressure(dut):
    testbase = await _new_testbase(dut)
    fifo_depth = int(os.environ.get("TX_SUBSYSTEM_FIFO_DEPTH", "64"))
    desc_depth = int(os.environ.get("TX_SUBSYSTEM_DESC_DEPTH", "32"))
    pressure_words = min(fifo_depth, desc_depth) + 1

    await testbase.set_pcs_ready(0)
    for idx in range(pressure_words):
        await testbase.sequence.add_dma_axis_word(
            data=idx,
            keep=DMA_KEEP_ALL,
            last=1,
        )

    blocked = cocotb.start_soon(
        testbase.sequence.add_dma_axis_word(
            data=0xDEAD_BEEF,
            keep=DMA_KEEP_ALL,
            last=1,
        )
    )

    saw_backpressure = False
    for _ in range(64):
        await RisingEdge(dut.dma_aclk)
        if int(dut.s_axis_dma_tready_o.value) == 0:
            saw_backpressure = True
            break
    assert saw_backpressure, "DMA tready must deassert when the queue is full"

    await testbase.set_pcs_ready(1)
    await blocked
    await testbase.drain_and_check(timeout_cycles=20000)


@cocotb.test()
async def test_standard_frame_sizes(dut):
    testbase = await _new_testbase(dut, dma_period_ns=6, tx_period_ns=10)
    rng = random.Random(0x1500_2026)

    for frame_bytes in (64, 512, 1500):
        words = (frame_bytes + 31) // 32
        tail_bytes = frame_bytes - ((words - 1) * 32)
        for idx in range(words):
            last = idx == (words - 1)
            keep = _tail_keep(tail_bytes) if last else DMA_KEEP_ALL
            await testbase.sequence.add_dma_axis_word(
                data=rng.getrandbits(256),
                keep=keep,
                last=last,
            )
        await testbase.sequence.add_idle(2)

    await testbase.drain_and_check(timeout_cycles=60000)


@cocotb.test()
async def test_pcs_backpressure(dut):
    testbase = await _new_testbase(dut)
    rng = random.Random(0x25ACDC)
    stop_ready = False
    hold_violations = []

    async def ready_jitter():
        while not stop_ready:
            dut.m_axis_pcs_tready_i.value = 1 if rng.random() < 0.65 else 0
            await RisingEdge(dut.tx_aclk)
        dut.m_axis_pcs_tready_i.value = 1

    async def output_hold_checker():
        prev = None
        while not stop_ready:
            await RisingEdge(dut.tx_aclk)
            valid = int(dut.m_axis_pcs_tvalid_o.value)
            ready = int(dut.m_axis_pcs_tready_i.value)
            curr = (
                int(dut.m_axis_pcs_tdata_o.value),
                int(dut.m_axis_pcs_tkeep_o.value),
                int(dut.m_axis_pcs_tlast_o.value),
            )
            if valid and not ready:
                if prev is not None and curr != prev:
                    hold_violations.append((prev, curr))
                prev = curr
            else:
                prev = None

    ready_task = cocotb.start_soon(ready_jitter())
    hold_task = cocotb.start_soon(output_hold_checker())

    for idx in range(24):
        await testbase.sequence.add_dma_axis_word(
            data=rng.getrandbits(256),
            keep=DMA_KEEP_ALL if (idx % 3) else 0x0000_FFFF,
            last=1,
        )

    await testbase.driver.wait_until_idle()
    stop_ready = True
    await ready_task
    await hold_task
    assert not hold_violations, f"Output changed while stalled: {hold_violations[:1]}"
    await testbase.drain_and_check(timeout_cycles=20000)


@cocotb.test()
async def test_async_clock_ratios(dut):
    testbase = await _new_testbase(dut, dma_period_ns=6, tx_period_ns=10)

    for idx in range(20):
        await testbase.sequence.add_dma_axis_word(
            data=(idx << 224) | (idx * 0x12345),
            keep=DMA_KEEP_ALL if idx % 4 else 0x00FF_FFFF,
            last=1,
        )

    await testbase.drain_and_check(timeout_cycles=20000)


@cocotb.test()
async def test_ingress_idle_gaps(dut):
    testbase = await _new_testbase(dut)

    for idx in range(6):
        await testbase.sequence.add_dma_axis_word(
            data=(0x55 << 248) | idx,
            keep=DMA_KEEP_ALL if idx != 5 else 0x000F_FFFF,
            last=(idx == 5),
        )
        await testbase.sequence.add_idle(idx % 3)

    await testbase.drain_and_check(timeout_cycles=16000)


@cocotb.test()
async def test_long_random_packets(dut):
    testbase = await _new_testbase(dut, dma_period_ns=6, tx_period_ns=10)
    rng = random.Random(0x2026_0427)

    for _ in range(48):
        words = rng.randint(1, 6)
        for idx in range(words):
            last = idx == (words - 1)
            keep = _tail_keep(rng.randint(1, 32)) if last else DMA_KEEP_ALL
            await testbase.sequence.add_dma_axis_word(
                data=rng.getrandbits(256),
                keep=keep,
                last=last,
            )
        if rng.random() < 0.5:
            await testbase.sequence.add_idle(rng.randint(1, 3))

    await testbase.drain_and_check(timeout_cycles=60000)


@cocotb.test()
async def test_reset_behavior(dut):
    testbase = await _new_testbase(dut)

    await testbase.reset()
    await testbase.sequence.add_dma_axis_word(
        data=0xCAFE_BABE,
        keep=0x0000_00FF,
        last=1,
    )

    await testbase.drain_and_check()
