import cocotb
from cocotb.triggers import RisingEdge, Timer

from tx_scheduling.tb.tx_scheduling_test_base import TxSchedulingTestBase
from tb_utils.tb_common import initialize_tb


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
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    await testbase.sequence.add_frame(queue_id=1, num_beats=2)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_sequential_test(dut):
    """Q0 frame then Q1 frame sequentially. Verify both pass through."""
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
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSchedulingTestBase(dut)

    await testbase.sequence.add_simultaneous_frames(q0_num=3, q1_num=2)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_scheduling_single_beat_frames_test(dut):
    """Single-beat frames (last=1 immediately) to test fast IDLE transitions."""
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

    Q0 = 1 << 0
    await testbase.sequence.add_beat(q_valid=Q0, fifo_full=True)
    await testbase.sequence.add_beat(q_valid=Q0)
    await testbase.sequence.add_beat(q_valid=Q0, q_last=Q0)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()
