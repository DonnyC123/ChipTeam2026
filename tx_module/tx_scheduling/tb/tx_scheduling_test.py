import cocotb
import random

from tx_scheduling_test_base import TxSchedulingTestBase
from tb_utils.tb_common import initialize_tb


def _num_queues(dut) -> int:
    return len(dut.q_valid_i)


def _max_burst_beats(dut) -> int:
    try:
        return int(dut.MAX_BURST_BEATS.value)
    except (AttributeError, TypeError, ValueError):
        return 256


@cocotb.test()
async def tx_scheduling_q0_only_test(dut):
    """Single 3-beat frame on Q0, Q1 idle. All reads should select Q0."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    await testbase.sequence.add_frame(queue_id=0, num_beats=3)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_q1_only_test(dut):
    """Single 2-beat frame on Q1, Q0 idle. All reads should select Q1."""
    if _num_queues(dut) < 2:
        return

    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    await testbase.sequence.add_frame(queue_id=1, num_beats=2)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_sequential_test(dut):
    """Q0 frame then Q1 frame sequentially. Verify both pass through."""
    if _num_queues(dut) < 2:
        return

    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    await testbase.sequence.add_frame(queue_id=0, num_beats=2)
    await testbase.sequence.add_frame(queue_id=1, num_beats=3)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_round_robin_test(dut):
    """Both queues present data simultaneously.

    After reset last_served=NUM_QUEUES-1, so scheduler prefers Q0 first.
    Q0 has 3 beats, Q1 has 2 beats. Scheduler serves Q0 atomically,
    then switches to Q1 (total 5 cycles).
    Expected output: [Q0, Q0, Q0, Q1, Q1].
    """
    if _num_queues(dut) < 2:
        return

    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    await testbase.sequence.add_simultaneous_frames(q0_num=3, q1_num=2)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_single_beat_frames_test(dut):
    """Single-beat frames (last=1 immediately) to test fast IDLE transitions."""
    if _num_queues(dut) < 2:
        return

    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    await testbase.sequence.add_frame(queue_id=0, num_beats=1)
    await testbase.sequence.add_frame(queue_id=1, num_beats=1)
    await testbase.sequence.add_frame(queue_id=0, num_beats=1)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_backpressure_test(dut):
    """FIFO full prevents scheduler from issuing reads."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    q0 = 1 << 0
    await testbase.sequence.add_beat(q_valid=q0, fifo_full=True)
    await testbase.sequence.add_beat(q_valid=q0)
    await testbase.sequence.add_beat(q_valid=q0, q_last=q0)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_req_without_grant_test(dut):
    """Request should assert even when grant is temporarily withheld."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    q0 = 1 << 0
    await testbase.sequence.add_beat(q_valid=q0, fifo_grant=False)
    await testbase.sequence.add_beat(q_valid=q0, q_last=q0, fifo_grant=True)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_round_robin_4q_smoke_test(dut):
    """For NUM_QUEUES>=4, verify one full RR round over Q0..Q3 single-beat frames."""
    if _num_queues(dut) < 4:
        return

    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    mask4 = (1 << 4) - 1
    for _ in range(4):
        await testbase.sequence.add_beat(q_valid=mask4, q_last=mask4)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_round_robin_8q_smoke_test(dut):
    """For NUM_QUEUES>=8, verify one full RR round over Q0..Q7 single-beat frames."""
    if _num_queues(dut) < 8:
        return

    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    mask8 = (1 << 8) - 1
    for _ in range(8):
        await testbase.sequence.add_beat(q_valid=mask8, q_last=mask8)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_long_random_test(dut):
    """Long randomized scheduler traffic across q_valid/q_last/backpressure/grant."""
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    num_queues = _num_queues(dut)
    mask_all = (1 << num_queues) - 1
    rng = random.Random(0x5CED_2026)
    num_cycles = max(500, num_queues * 200)

    for _ in range(num_cycles):
        q_valid = rng.getrandbits(num_queues) & mask_all
        q_last = rng.getrandbits(num_queues) & q_valid
        fifo_full = rng.random() < 0.10
        fifo_grant = rng.random() < 0.90
        await testbase.sequence.add_beat(
            q_valid=q_valid,
            q_last=q_last,
            fifo_full=fifo_full,
            fifo_grant=fifo_grant,
        )

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_max_burst_rotation_test(dut):
    """When q_last is missing, watchdog must force rotation after MAX_BURST_BEATS."""
    if _num_queues(dut) < 2:
        return

    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    max_burst = _max_burst_beats(dut)
    q0 = 1 << 0
    q1 = 1 << 1

    # Keep Q0 + Q1 valid. Q0 never asserts last; Q1 is always single-beat.
    # Scheduler should serve Q0 for max_burst beats, then force a Q1 turn.
    for _ in range(max_burst + 2):
        await testbase.sequence.add_beat(q_valid=(q0 | q1), q_last=q1)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()
