import random

import cocotb
from cocotb.triggers import RisingEdge

from tb.tx_subsystem_test_base import TxSubsystemTestBase
from tb_utils.tb_common import initialize_tb


@cocotb.test()
async def tx_subsystem_axis_basic_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSubsystemTestBase(dut)

    words = [
        (
            0x_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111,
            0xFFFF_FFFF,
            0,
        ),
        (
            0x_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222,
            0x0FFF_FFFF,
            0,
        ),
        (
            0x_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333,
            0x00FF_00FF,
            1,
        ),
    ]

    for data, keep, last in words:
        await testbase.sequence.add_dma_axis_word(
            data=data,
            keep=keep,
            last=last,
            q_valid=0,
            q_last=0,
            dma_req_ready=1,
            m_axis_tready=1,
        )

    await testbase.sequence.add_idle(cycles=len(words) * 8, m_axis_tready=1)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_subsystem_axis_long_random_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSubsystemTestBase(dut)

    rng = random.Random(0x7522_2026)
    num_words = 64

    for idx in range(num_words):
        data = rng.getrandbits(256)
        keep = rng.getrandbits(32)
        last = 1 if idx == (num_words - 1) else 0
        await testbase.sequence.add_dma_axis_word(
            data=data,
            keep=keep,
            last=last,
            q_valid=0,
            q_last=0,
            dma_req_ready=1,
            m_axis_tready=1,
        )
        # One DMA word expands to 4 PCS beats, so pace injection to avoid
        # overdriving the AXIS ingress beyond sustainable throughput.
        await testbase.sequence.add_idle(cycles=3, m_axis_tready=1)

    await testbase.sequence.add_idle(cycles=num_words * 4, m_axis_tready=1)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_subsystem_dma_req_ready_gating_test(dut):
    """Use sequence-driven idle stimulus to isolate dma_req_ready gating behavior."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSubsystemTestBase(dut)

    q0 = 0b01

    # Keep AXIS ingress idle via sequence; only scheduler-side request path is active.
    await testbase.sequence.add_idle(
        cycles=4,
        q_valid=q0,
        q_last=q0,
        dma_req_ready=0,
        m_axis_tready=1,
    )
    await testbase.sequence.add_idle(
        cycles=8,
        q_valid=q0,
        q_last=q0,
        dma_req_ready=1,
        m_axis_tready=1,
    )

    blocked_reads = 0
    enabled_reads = 0

    # Sample while queued sequence items are being driven.
    for _ in range(20):
        await RisingEdge(dut.clk)
        if int(dut.dma_read_en_o.value):
            if int(dut.dma_req_ready_i.value):
                enabled_reads += 1
            else:
                blocked_reads += 1

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()

    assert blocked_reads == 0, "dma_read_en_o must stay low while dma_req_ready_i=0"
    assert enabled_reads > 0, "dma_read_en_o should assert once dma_req_ready_i is enabled"

@cocotb.test()
async def tx_subsystem_axis_random_ready_test(dut):
    """Sequence-driven random downstream backpressure with scoreboard checking."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSubsystemTestBase(dut)

    rng = random.Random(0x25AA_2026)
    num_words = 24

    for idx in range(num_words):
        data = rng.getrandbits(256)
        keep = rng.getrandbits(32)
        last = 1 if idx == (num_words - 1) else 0
        ready = 1 if rng.random() < 0.7 else 0

        await testbase.sequence.add_dma_axis_word(
            data=data,
            keep=keep,
            last=last,
            q_valid=0,
            q_last=0,
            dma_req_ready=1,
            m_axis_tready=ready,
        )

        gap_cycles = rng.randint(0, 2)
        if gap_cycles:
            await testbase.sequence.add_idle(
                cycles=gap_cycles,
                q_valid=0,
                q_last=0,
                dma_req_ready=1,
                m_axis_tready=(1 if rng.random() < 0.7 else 0),
            )

    # Drain with additional randomized backpressure.
    for _ in range(num_words * 10):
        await testbase.sequence.add_idle(
            cycles=1,
            q_valid=0,
            q_last=0,
            dma_req_ready=1,
            m_axis_tready=(1 if rng.random() < 0.75 else 0),
        )

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()

@cocotb.test()
async def tx_subsystem_axis_end_to_end_stress_test(dut):
    """Long sequence-driven AXIS stress with randomized backpressure and scheduler sideband."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSubsystemTestBase(dut)

    rng = random.Random(0xE2E0_2026)
    num_queues = len(dut.q_valid_i)
    all_q_mask = (1 << num_queues) - 1

    total_words = 256
    words = []
    remaining = total_words
    while remaining > 0:
        pkt_len = min(remaining, rng.randint(1, 8))
        for idx in range(pkt_len):
            words.append(
                (
                    rng.getrandbits(256),
                    rng.getrandbits(32),
                    1 if idx == (pkt_len - 1) else 0,
                )
            )
        remaining -= pkt_len

    for data, keep, last in words:
        q_valid = rng.getrandbits(num_queues) & all_q_mask
        if rng.random() < 0.25:
            q_valid = all_q_mask
        q_last = rng.getrandbits(num_queues) & q_valid
        dma_req_ready = 1 if rng.random() < 0.88 else 0
        m_axis_tready = 1 if rng.random() < 0.75 else 0

        await testbase.sequence.add_dma_axis_word(
            data=data,
            keep=keep,
            last=last,
            q_valid=q_valid,
            q_last=q_last,
            dma_req_ready=dma_req_ready,
            m_axis_tready=m_axis_tready,
        )

        # Keep random pressure but pace ingress enough so AXIS writes are accepted.
        for _ in range(rng.randint(4, 8)):
            idle_q_valid = rng.getrandbits(num_queues) & all_q_mask
            idle_q_last = rng.getrandbits(num_queues) & idle_q_valid
            await testbase.sequence.add_idle(
                cycles=1,
                q_valid=idle_q_valid,
                q_last=idle_q_last,
                dma_req_ready=(1 if rng.random() < 0.88 else 0),
                m_axis_tready=(1 if rng.random() < 0.8 else 0),
            )

    for _ in range(total_words * 20):
        q_valid = rng.getrandbits(num_queues) & all_q_mask
        q_last = rng.getrandbits(num_queues) & q_valid
        await testbase.sequence.add_idle(
            cycles=1,
            q_valid=q_valid,
            q_last=q_last,
            dma_req_ready=(1 if rng.random() < 0.9 else 0),
            m_axis_tready=(1 if rng.random() < 0.85 else 0),
        )

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()
