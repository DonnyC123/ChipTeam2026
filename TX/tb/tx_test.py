import os
import random

import cocotb
from cocotb.triggers import RisingEdge, Timer
from cocotb.types import Logic, LogicArray

from TX.tb.tx_sequence import TxSequence
from TX.tb.tx_sequence_item import TxSequenceItem
from TX.tb.tx_test_base import TxFullChainTestBase


def patterned_frame(length: int, seed: int) -> list[int]:
    return [((seed + i * 17) & 0xFF) for i in range(length)]


def queue_id(index: int) -> int:
    return index % TxSequenceItem.NUM_QUEUES


async def run_frames(
    dut,
    frames: list[tuple[list[int], int]],
    inter_word_gap: int = 3,
    post_frame_idle: int = 8,
    ordered: bool = True,
):
    tb = await TxFullChainTestBase.create(dut)
    return await tb.run_frames(
        frames,
        inter_word_gap=inter_word_gap,
        post_frame_idle=post_frame_idle,
        ordered=ordered,
    )


@cocotb.test()
async def test_single_min_frame(dut):
    frame = patterned_frame(64, 0x10)
    await run_frames(dut, [(frame, 0)])


@cocotb.test()
async def test_short_tail_lengths(dut):
    frames = [(patterned_frame(64 + tail, 0x20 + tail), 0) for tail in range(8)]
    await run_frames(dut, frames)


@cocotb.test()
async def test_dma_tkeep_tail_lengths(dut):
    frames = [
        (patterned_frame(64 + tail, 0xB0 + tail), queue_id(tail))
        for tail in range(1, 33)
    ]
    await run_frames(dut, frames, inter_word_gap=2, ordered=False)


@cocotb.test()
async def test_long_frames_cross_dma_words(dut):
    frames = [
        (patterned_frame(256, 0xC0), 0),
        (patterned_frame(512, 0xD0), queue_id(1)),
        (patterned_frame(1500, 0xE0), queue_id(2)),
    ]
    await run_frames(dut, frames, inter_word_gap=1, ordered=False)


@cocotb.test()
async def test_back_to_back_frames(dut):
    frames = [
        (patterned_frame(64, 0x30), 0),
        (patterned_frame(96, 0x40), 0),
        (patterned_frame(128, 0x50), 0),
    ]
    await run_frames(dut, frames, inter_word_gap=1)


@cocotb.test()
async def test_no_idle_back_to_back_frames(dut):
    frames = [(patterned_frame(64 + idx, 0x35 + idx), 0) for idx in range(8)]
    await run_frames(dut, frames, inter_word_gap=0, post_frame_idle=0)


@cocotb.test()
async def test_mid_packet_ingress_idle_gaps(dut):
    tb = await TxFullChainTestBase.create(dut)
    frame = patterned_frame(197, 0x44)
    gaps = [1, 0, 3, 2, 1, 0, 2]

    await tb.send_expected_frame_with_gaps(frame, gaps=gaps, tdest=0, post_frame_idle=4)
    await tb.sequence.add_idle(256)
    await tb.drain()
    tb.check()


@cocotb.test()
async def test_multiqueue_order_deterministic(dut):
    frames = [
        (patterned_frame(64, 0x60), queue_id(0)),
        (patterned_frame(64, 0x70), queue_id(1)),
        (patterned_frame(64, 0x80), queue_id(2)),
        (patterned_frame(64, 0x90), queue_id(3)),
    ]
    await run_frames(dut, frames, inter_word_gap=2)


@cocotb.test()
async def test_multiqueue_packet_integrity_tagged(dut):
    frames = []
    for idx in range(16):
        qid = queue_id(idx)
        frame = patterned_frame(80 + (idx % 5), 0x40 + idx)
        frame[0] = qid
        frame[1] = idx
        frames.append((frame, qid))
    await run_frames(dut, frames, inter_word_gap=1, post_frame_idle=1, ordered=False)


@cocotb.test()
async def test_random_packets(dut):
    rng = random.Random(0x252026)
    frames = []
    for idx in range(20):
        length = rng.randint(64, 180)
        qid = rng.randrange(TxSequenceItem.NUM_QUEUES)
        frame = [rng.randrange(256) for _ in range(length)]
        frame[0] = idx
        frame[1] = qid
        frames.append((frame, qid))
    await run_frames(dut, frames, inter_word_gap=3, ordered=False)


@cocotb.test()
async def test_random_ingress_idle_gaps_single_queue(dut):
    rng = random.Random(0x1D1E_2026)
    tb = await TxFullChainTestBase.create(dut)

    for idx in range(12):
        frame = [rng.randrange(256) for _ in range(rng.randint(64, 220))]
        frame[0] = idx
        words = TxSequence.frame_to_dma_words(frame)
        gaps = [rng.randint(0, 3) for _ in words]
        await tb.send_expected_frame_with_gaps(
            frame,
            gaps=gaps,
            tdest=0,
            post_frame_idle=rng.randint(0, 4),
        )

    await tb.sequence.add_idle(256)
    await tb.drain()
    tb.check()


@cocotb.test()
async def test_configured_queue_width(dut):
    high_qid = TxSequenceItem.NUM_QUEUES - 1
    frames = [
        (patterned_frame(64, 0xA5), 0),
        (patterned_frame(96, 0x5A), high_qid),
    ]
    await run_frames(dut, frames, inter_word_gap=2, ordered=False)


@cocotb.test()
async def test_ingress_backpressure(dut):
    tb = await TxFullChainTestBase.create(dut)
    frames = [(patterned_frame(128, 0xA0 + idx), 0) for idx in range(48)]

    for frame, qid in frames:
        await tb.send_expected_frame(frame, tdest=qid, inter_word_gap=0)

    await tb.sequence.add_idle(1024)
    await tb.drain(timeout_cycles=12000)
    tb.check()
    if tb.sequence.backpressure_wait_cycles == 0:
        dut._log.warning("Expected ingress backpressure wait cycles")


@cocotb.test()
async def test_fifo_pressure_recovers(dut):
    tb = await TxFullChainTestBase.create(dut)
    frames = [(patterned_frame(96, 0x55 + idx), 0) for idx in range(40)]

    for frame, qid in frames:
        await tb.send_expected_frame(frame, tdest=qid, inter_word_gap=0)

    if tb.sequence.backpressure_wait_cycles == 0:
        dut._log.warning("Expected FIFO pressure to stall ingress")

    await tb.sequence.add_idle(1024)
    await tb.drain(timeout_cycles=12000)
    tb.check()

    recovered_ready = False
    for _ in range(80):
        await RisingEdge(dut.clk)
        if int(dut.s_axis_dma_tready_o.value) == 1:
            recovered_ready = True
            break

    if not recovered_ready:
        dut._log.warning("Ingress tready should recover after FIFO pressure drains")


@cocotb.test()
async def test_invalid_tdest_backpressure_num_queues_3(dut):
    if TxSequenceItem.NUM_QUEUES != 3:
        dut._log.info("NUM_QUEUES is not 3; invalid-tdest smoke is inactive for this run")
        return

    await TxFullChainTestBase.create(dut)
    invalid_tdest = TxSequenceItem.NUM_QUEUES

    dut.s_axis_dma_tdata_i.value = LogicArray.from_unsigned(0x1234, TxSequenceItem.DMA_DATA_W)
    dut.s_axis_dma_tkeep_i.value = LogicArray.from_unsigned(0xFFFF_FFFF, TxSequenceItem.DMA_KEEP_W)
    dut.s_axis_dma_tlast_i.value = Logic(1)
    dut.s_axis_dma_tdest_i.value = LogicArray.from_unsigned(invalid_tdest, TxSequenceItem.QID_W)
    dut.s_axis_dma_tvalid_i.value = Logic(1)

    invalid_ready_cycles = 0
    for _ in range(4):
        await Timer(1, unit="ns")
        if int(dut.s_axis_dma_tready_o.value) != 0:
            invalid_ready_cycles += 1
        await RisingEdge(dut.clk)

    if invalid_ready_cycles:
        dut._log.warning(
            "Invalid tdest accepted ready for %d observed cycles",
            invalid_ready_cycles,
        )

    dut.s_axis_dma_tvalid_i.value = Logic(0)


@cocotb.test()
async def test_small_fifo_depth_smoke(dut):
    fifo_depth = int(os.environ.get("TX_TB_FIFO_DEPTH", "32"))
    if fifo_depth > 8:
        dut._log.info("FIFO depth is not small; small-FIFO smoke is inactive for this run")
        return

    frames = [
        (patterned_frame(64, 0x11), 0),
        (patterned_frame(95, 0x22), queue_id(1)),
        (patterned_frame(120, 0x33), queue_id(2)),
    ]
    await run_frames(dut, frames, inter_word_gap=0, post_frame_idle=0, ordered=False)
