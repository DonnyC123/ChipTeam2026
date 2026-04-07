import random

import cocotb
from cocotb.triggers import RisingEdge, Timer

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
    await initialize_tb(dut, clk_period_ns=10)

    dut.s_axis_dma_tdata_i.value = 0
    dut.s_axis_dma_tkeep_i.value = 0
    dut.s_axis_dma_tvalid_i.value = 0
    dut.s_axis_dma_tlast_i.value = 0
    dut.m_axis_tready_i.value = 1
    dut.q_valid_i.value = 0b01
    dut.q_last_i.value = 0b01

    dut.dma_req_ready_i.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
        assert int(dut.dma_read_en_o.value) == 0, "dma_read_en_o should stay low when dma_req_ready_i=0"

    dut.dma_req_ready_i.value = 1
    seen_read = False
    for _ in range(5):
        await RisingEdge(dut.clk)
        if int(dut.dma_read_en_o.value):
            seen_read = True
            break

    assert seen_read, "dma_read_en_o should assert when dma_req_ready_i goes high"


@cocotb.test()
async def tx_subsystem_axis_random_ready_test(dut):
    """Randomized downstream backpressure; verify no beat loss/reorder."""
    await initialize_tb(dut, clk_period_ns=10)

    rng = random.Random(0x25AA_2026)
    num_words = 40
    words = []
    for idx in range(num_words):
        words.append(
            (
                rng.getrandbits(256),
                rng.getrandbits(32),
                1 if idx == (num_words - 1) else 0,
            )
        )

    expected = []
    for data, keep, last in words:
        for beat in range(4):
            beat_data = (data >> (64 * beat)) & ((1 << 64) - 1)
            beat_keep = (keep >> (8 * beat)) & 0xFF
            beat_last = 1 if (last and beat == 3) else 0
            expected.append((beat_data, beat_keep, beat_last))

    dut.q_valid_i.value = 0
    dut.q_last_i.value = 0
    dut.dma_req_ready_i.value = 1

    send_idx = 0
    recv = []
    max_cycles = 5000
    cycles = 0

    while (send_idx < num_words or len(recv) < len(expected)) and cycles < max_cycles:
        ready = 1 if rng.random() < 0.7 else 0
        dut.m_axis_tready_i.value = ready

        if send_idx < num_words:
            data, keep, last = words[send_idx]
            dut.s_axis_dma_tdata_i.value = data
            dut.s_axis_dma_tkeep_i.value = keep
            dut.s_axis_dma_tlast_i.value = last
            dut.s_axis_dma_tvalid_i.value = 1
        else:
            dut.s_axis_dma_tdata_i.value = 0
            dut.s_axis_dma_tkeep_i.value = 0
            dut.s_axis_dma_tlast_i.value = 0
            dut.s_axis_dma_tvalid_i.value = 0

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        cycles += 1

        if send_idx < num_words and int(dut.s_axis_dma_tvalid_i.value) and int(dut.s_axis_dma_tready_o.value):
            send_idx += 1

        if int(dut.m_axis_tvalid_o.value) and int(dut.m_axis_tready_i.value):
            recv.append(
                (
                    int(dut.m_axis_tdata_o.value),
                    int(dut.m_axis_tkeep_o.value),
                    int(dut.m_axis_tlast_o.value),
                )
            )

    assert cycles < max_cycles, "Random ready test timed out"
    assert len(recv) == len(expected), f"Beat count mismatch: recv={len(recv)}, expected={len(expected)}"
    assert recv == expected, "Data/keep/last stream mismatch under randomized ready"

@cocotb.test()
async def tx_subsystem_axis_end_to_end_stress_test(dut):
    """Long random AXIS + scheduler-pressure stress with end-to-end data checking."""
    await initialize_tb(dut, clk_period_ns=10)

    rng = random.Random(0xE2E0_2026)
    num_queues = len(dut.q_valid_i)
    all_q_mask = (1 << num_queues) - 1

    total_words = 320
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

    expected_beats = []
    recv_beats = []
    ingress_accepts = 0
    egress_accepts = 0
    sched_reads = 0
    overflow_events = 0

    send_idx = 0
    max_cycles = 30000

    for cycle in range(max_cycles):
        # Randomized backpressure and request readiness.
        m_axis_tready = 1 if rng.random() < 0.72 else 0
        dma_req_ready = 1 if rng.random() < 0.88 else 0

        # Randomized queue status for scheduler-side stress.
        q_valid = rng.getrandbits(num_queues) & all_q_mask
        if rng.random() < 0.25:
            q_valid = all_q_mask
        q_last = rng.getrandbits(num_queues) & q_valid

        dut.m_axis_tready_i.value = m_axis_tready
        dut.dma_req_ready_i.value = dma_req_ready
        dut.q_valid_i.value = q_valid
        dut.q_last_i.value = q_last

        if send_idx < total_words:
            data, keep, last = words[send_idx]
            dut.s_axis_dma_tdata_i.value = data
            dut.s_axis_dma_tkeep_i.value = keep
            dut.s_axis_dma_tlast_i.value = last
            dut.s_axis_dma_tvalid_i.value = 1
        else:
            dut.s_axis_dma_tdata_i.value = 0
            dut.s_axis_dma_tkeep_i.value = 0
            dut.s_axis_dma_tlast_i.value = 0
            dut.s_axis_dma_tvalid_i.value = 0

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        # AXIS ingress acceptance and expected beat expansion.
        if send_idx < total_words and int(dut.s_axis_dma_tvalid_i.value) and int(dut.s_axis_dma_tready_o.value):
            data, keep, last = words[send_idx]
            ingress_accepts += 1
            for beat in range(4):
                beat_data = (data >> (64 * beat)) & ((1 << 64) - 1)
                beat_keep = (keep >> (8 * beat)) & 0xFF
                beat_last = 1 if (last and beat == 3) else 0
                expected_beats.append((beat_data, beat_keep, beat_last))
            send_idx += 1

        # AXIS egress acceptance.
        if int(dut.m_axis_tvalid_o.value) and int(dut.m_axis_tready_i.value):
            egress_accepts += 1
            recv_beats.append(
                (
                    int(dut.m_axis_tdata_o.value),
                    int(dut.m_axis_tkeep_o.value),
                    int(dut.m_axis_tlast_o.value),
                )
            )

        # Scheduler contract sanity checks during stress.
        if int(dut.dma_read_en_o.value):
            sched_reads += 1
            sel = int(dut.dma_queue_sel_o.value)
            assert sel < num_queues, f"dma_queue_sel_o out of range: {sel}"
            assert int(dut.dma_req_ready_i.value) == 1, "dma_read_en_o high while dma_req_ready_i=0"
            assert ((int(dut.q_valid_i.value) >> sel) & 1) == 1, "dma_read_en_o selected queue without q_valid"

        # FIFO overflow should never happen in AXIS mode with proper tready backpressure.
        try:
            if int(dut.dut.tx_fifo_inst.overflow_o.value):
                overflow_events += 1
        except Exception:
            pass

        if send_idx >= total_words and len(recv_beats) >= len(expected_beats) and cycle > 200:
            break

    assert send_idx == total_words, f"Not all DMA words accepted: {send_idx}/{total_words}"
    assert len(recv_beats) == len(expected_beats), (
        f"Beat count mismatch: recv={len(recv_beats)}, expected={len(expected_beats)}"
    )
    assert recv_beats == expected_beats, "End-to-end AXIS stream mismatch under stress"
    assert overflow_events == 0, f"Unexpected FIFO overflow events in AXIS mode: {overflow_events}"

    dut._log.info(
        "stress stats: ingress_words=%d egress_beats=%d dma_reads=%d",
        ingress_accepts,
        egress_accepts,
        sched_reads,
    )

