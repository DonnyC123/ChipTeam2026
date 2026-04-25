import random

import cocotb
from cocotb.triggers import Event, RisingEdge

from tb_utils.tb_common import initialize_tb
from tx_subsystem_test_base import TxSubsystemTestBase
from tx_subsystem_sequence_item import TxSubsystemSequenceItem


BEATS_PER_WORD = 4
PCS_DATA_W = 64
PCS_VALID_W = 8


def _rand_last_keep_mask(rng: random.Random) -> int:
    """Generate non-zero LSB-contiguous keep for AXIS packet tail words."""
    valid_bytes = rng.randint(1, 32)
    return (1 << valid_bytes) - 1


def _mask_data_by_keep(data: int, keep: int) -> int:
    masked = 0
    for byte_idx in range(32):
        if (keep >> byte_idx) & 1:
            masked |= ((data >> (8 * byte_idx)) & 0xFF) << (8 * byte_idx)
    return masked


async def _collect_dma_words_from_monitor(
    testbase: TxSubsystemTestBase,
    expected_words: int,
    timeout_cycles: int = 4000,
):
    words = []
    beat_idx = 0
    assembled_data = 0
    assembled_keep = 0
    assembled_last = 0

    for _ in range(timeout_cycles):
        await RisingEdge(testbase.dut.clk)
        while not testbase.monitor.actual_queue.empty():
            beat_data, beat_keep, beat_last = await testbase.monitor.actual_queue.get()

            assembled_data |= int(beat_data) << (beat_idx * PCS_DATA_W)
            assembled_keep |= int(beat_keep) << (beat_idx * PCS_VALID_W)
            assembled_last = int(beat_last)

            # Word boundary:
            # - normal/non-last words always consume 4 PCS beats
            # - last words may terminate early on beat_last
            if beat_last or (beat_idx == (BEATS_PER_WORD - 1)):
                words.append((assembled_data, assembled_keep, assembled_last))
                assembled_data = 0
                assembled_keep = 0
                assembled_last = 0
                beat_idx = 0
                if len(words) >= expected_words:
                    return words
            else:
                beat_idx += 1

    raise AssertionError(
        f"Timed out collecting words: got {len(words)}, expected {expected_words}"
    )


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
            0xFFFF_FFFF,
            0,
        ),
        (
            0x_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333,
            0x0000_0FFF,
            1,
        ),
    ]

    for data, keep, last in words:
        await testbase.sequence.add_dma_axis_word(
            data=data,
            keep=keep,
            last=last,
            tdest=0,
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
    num_words = 96

    for _ in range(num_words):
        data = rng.getrandbits(256)
        keep = _rand_last_keep_mask(rng)
        # One-word packets to keep expected ordering deterministic.
        last = 1
        await testbase.sequence.add_dma_axis_word(
            data=data,
            keep=keep,
            last=last,
            tdest=0,
            m_axis_tready=1,
        )
        # One DMA word expands to 4 PCS beats, so pace injection to avoid
        # overdriving the AXIS ingress beyond sustainable throughput.
        await testbase.sequence.add_idle(cycles=3, m_axis_tready=1)

    await testbase.sequence.add_idle(cycles=num_words * 4, m_axis_tready=1)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_subsystem_multi_queue_round_robin_test(dut):
    """Preload two queues and verify round-robin packet service without starvation."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSubsystemTestBase(dut)

    words_per_queue = 4
    total_words = words_per_queue * 2

    # Preload while output is stalled to ensure both queues are populated.
    for idx in range(words_per_queue):
        q0_data = (0 << 252) | idx
        q1_data = (1 << 252) | idx

        await testbase.sequence.add_dma_axis_word(
            data=q0_data,
            keep=0xFFFF_FFFF,
            last=1,
            tdest=0,
            m_axis_tready=0,
            notify_expected=False,
        )
        await testbase.sequence.add_dma_axis_word(
            data=q1_data,
            keep=0xFFFF_FFFF,
            last=1,
            tdest=1,
            m_axis_tready=0,
            notify_expected=False,
        )

    # Release output and drain.
    await testbase.sequence.add_idle(cycles=total_words * 6, m_axis_tready=1)
    observed_words = await _collect_dma_words_from_monitor(
        testbase, expected_words=total_words, timeout_cycles=8000
    )
    await testbase.wait_for_driver_done()

    observed_qids = [((word[0] >> 252) & 0xF) for word in observed_words]
    assert observed_qids == [0, 1, 0, 1, 0, 1, 0, 1], (
        f"Unexpected queue service order: {observed_qids}"
    )

@cocotb.test()
async def tx_subsystem_axis_random_ready_test(dut):
    """Long AXIS random traffic with randomized downstream backpressure."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSubsystemTestBase(dut)

    rng = random.Random(0x25AA_2026)
    num_words = 96

    for idx in range(num_words):
        data = rng.getrandbits(256)
        last = 1 if (idx % rng.randint(1, 6) == 0) else 0
        keep = _rand_last_keep_mask(rng) if last else 0xFFFF_FFFF

        await testbase.sequence.add_dma_axis_word(
            data=data,
            keep=keep,
            last=last,
            tdest=0,
            m_axis_tready=1,
        )

        # Pace ingress to keep all words accepted while preserving output stress.
        await testbase.sequence.add_idle(
            cycles=3,
            tdest=0,
            m_axis_tready=(1 if rng.random() < 0.9 else 0),
        )

    # Drain with additional randomized backpressure.
    for _ in range(num_words * 8):
        await testbase.sequence.add_idle(
            cycles=1,
            tdest=0,
            m_axis_tready=(1 if rng.random() < 0.75 else 0),
        )

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()

@cocotb.test()
async def tx_subsystem_axis_queue_full_backpressure_test(dut):
    """Force one queue full and verify ingress backpressure instead of silent drops."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSubsystemTestBase(dut)

    fifo_depth = 32

    # Keep downstream stalled so selected queue fills up.
    for idx in range(fifo_depth):
        await testbase.sequence.add_dma_axis_word(
            data=(0xA << 252) | idx,
            keep=0xFFFF_FFFF,
            last=1,
            tdest=0,
            m_axis_tready=0,
            notify_expected=False,
        )

    # Hold stall for a short window and observe ingress backpressure.
    await testbase.sequence.add_idle(cycles=12, tdest=0, m_axis_tready=0)

    saw_backpressure = False
    for _ in range(fifo_depth + 40):
        await RisingEdge(dut.clk)
        if int(dut.s_axis_dma_tready_o.value) == 0:
            saw_backpressure = True
            break
    assert saw_backpressure, "Ingress tready should deassert when target queue is full"

    # Release downstream and verify queue can drain and accept again.
    await testbase.sequence.add_idle(cycles=fifo_depth * 6, tdest=0, m_axis_tready=1)
    await testbase.wait_for_driver_done()

    recovered_ready = False
    for _ in range(80):
        await RisingEdge(dut.clk)
        if int(dut.s_axis_dma_tready_o.value) == 1:
            recovered_ready = True
            break
    assert recovered_ready, "Ingress tready should recover after drain"


@cocotb.test()
async def tx_subsystem_dma_axis_multiqueue_packet_integration_test(dut):
    """
    Generic-sequence integration test with DMA-like packet traffic:
    - multi-queue via TDEST
    - packet-level TDEST stability
    - randomized egress backpressure
    - per-queue order and TLAST/KEEP integrity
    """
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSubsystemTestBase(dut)

    rng = random.Random(0xD6A2_2026)
    num_queues = TxSubsystemSequenceItem.NUM_QUEUES
    qid_mask = (1 << TxSubsystemSequenceItem.QID_W) - 1

    accepted_ingress_words = []
    stop_capture = Event()

    async def capture_ingress_accepts():
        while True:
            await RisingEdge(dut.clk)
            if stop_capture.is_set():
                return

            if int(dut.s_axis_dma_tvalid_i.value) and int(dut.s_axis_dma_tready_o.value):
                accepted_ingress_words.append(
                    (
                        int(dut.s_axis_dma_tdata_i.value),
                        int(dut.s_axis_dma_tkeep_i.value),
                        int(dut.s_axis_dma_tlast_i.value),
                        int(dut.s_axis_dma_tdest_i.value),
                    )
                )

    capture_task = cocotb.start_soon(capture_ingress_accepts())

    packet_count = 36
    for pkt_id in range(packet_count):
        queue_id = rng.randrange(num_queues)
        words_in_packet = rng.randint(1, 6)

        for word_idx in range(words_in_packet):
            is_last = int(word_idx == (words_in_packet - 1))
            keep = _rand_last_keep_mask(rng) if is_last else 0xFFFF_FFFF

            tagged_data = rng.getrandbits(256)
            # Keep tags in low bytes so they survive last-word partial keep masking.
            tagged_data &= ~((1 << 16) - 1)
            tagged_data |= ((pkt_id & 0xFF) << 8)
            tagged_data |= ((word_idx & 0xF) << 4)
            tagged_data |= (queue_id & qid_mask)

            await testbase.sequence.add_dma_axis_word(
                data=tagged_data,
                keep=keep,
                last=is_last,
                tdest=queue_id,
                m_axis_tready=(1 if rng.random() < 0.86 else 0),
                notify_expected=False,
            )

            # Conservative pacing keeps ingress acceptance robust while preserving random pressure.
            for _ in range(4 + rng.randint(0, 2)):
                await testbase.sequence.add_idle(
                    cycles=1,
                    tdest=queue_id,
                    m_axis_tready=(1 if rng.random() < 0.82 else 0),
                )

    # Drain all outstanding data.
    await testbase.sequence.add_idle(cycles=packet_count * 36, tdest=0, m_axis_tready=1)
    await testbase.wait_for_driver_done()

    stop_capture.set()
    await RisingEdge(dut.clk)
    await capture_task

    assert len(accepted_ingress_words) > 0, "No AXIS ingress words were accepted"

    observed_words = await _collect_dma_words_from_monitor(
        testbase,
        expected_words=len(accepted_ingress_words),
        timeout_cycles=(len(accepted_ingress_words) * 24) + 3000,
    )

    expected_by_queue = {q: [] for q in range(num_queues)}
    for data, keep, last, qid in accepted_ingress_words:
        expected_by_queue[qid].append((_mask_data_by_keep(data, keep), keep, last))

    observed_by_queue = {q: [] for q in range(num_queues)}
    for data, keep, last in observed_words:
        data = _mask_data_by_keep(data, keep)
        qid = data & qid_mask
        assert qid in observed_by_queue, f"Observed invalid queue tag in payload: {qid}"
        observed_by_queue[qid].append((data, keep, last))

    for q in range(num_queues):
        assert observed_by_queue[q] == expected_by_queue[q], (
            f"Queue {q} order/data mismatch: "
            f"exp={len(expected_by_queue[q])} obs={len(observed_by_queue[q])}"
        )

        for _, keep, last in observed_by_queue[q]:
            if not last:
                assert keep == 0xFFFF_FFFF, (
                    f"Queue {q}: non-last beat must keep full mask, got 0x{keep:08x}"
                )
