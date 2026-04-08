# rx_test.py
import cocotb
from cocotb.clock    import Clock
from cocotb.triggers import RisingEdge, ClockCycles
from queue import SimpleQueue

from tb_utils.generic_drivers       import GenericDriver
from tb_utils.abstract_transactions import AbstractTransaction
from tb_utils.generic_monitor       import GenericValidMonitor

from rx_tb.tb.rx_transaction    import RxTransaction
from rx_tb.tb.rx_sequence_item  import RxSequenceItem
from rx_tb.tb.rx_sequence       import RxSequence
from rx_tb.tb.rx_scoreboard     import RxScoreboard

CLK_PERIOD_NS = 10
RESET_CYCLES  = 5
LOCK_IDLES    = 64
FLUSH_CYCLES  = 40


class PayloadMonitor(GenericValidMonitor):
    async def _monitor(self):
        while True:
            await RisingEdge(self.dut.clk)

            txn = RxTransaction()
            txn.out_valid_o   = self.dut.out_valid_o.value
            txn.out_data_o    = self.dut.out_data_o.value
            txn.bytes_valid_o = self.dut.bytes_valid_o.value

            # FIX: valid_bytes returns a list — a non-empty list is always
            # truthy, so the old "txn.valid or txn.valid_bytes" condition
            # enqueued a transaction on *every* clock cycle.
            # Use n_valid (popcount of bytes_valid_o) instead.
            if txn.valid or txn.n_valid > 0:
                self.actual_queue.put_nowait(txn)


async def init_dut(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())

    dut.raw_valid_i.value = 0
    dut.raw_data_i.value  = 0
    dut.rst.value         = 1
    await ClockCycles(dut.clk, RESET_CYCLES)
    dut.rst.value = 0
    await RisingEdge(dut.clk)

    driver     = GenericDriver(dut, RxSequenceItem)
    monitor    = PayloadMonitor(dut, RxTransaction)
    scoreboard = RxScoreboard()
    seq        = RxSequence(driver)

    return seq, monitor, scoreboard


async def drain_and_check(dut, monitor, scoreboard, cycles: int = FLUSH_CYCLES):
    # Wait for in-flight data to propagate through the DUT pipeline
    await ClockCycles(dut.clk, cycles)

    # FIX: yield once more so the monitor coroutine gets a chance to run and
    # enqueue any transactions that landed on the last rising edge of the
    # flush window before we drain the queue.
    await RisingEdge(dut.clk)

    while not monitor.actual_queue.empty():
        txn = monitor.actual_queue.get_nowait()
        scoreboard.ingest(txn)

    scoreboard.flush()
    scoreboard.check_all_received()
    dut._log.info(scoreboard.summary())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@cocotb.test()
async def test_lock_and_single_frame(dut):
    seq, monitor, scoreboard = await init_dut(dut)
    seq.scrambler_state = 1

    gold = [0xAA, 0xBB, 0xCC, 0xDD] * 16
    scoreboard.add_expected(gold)

    await seq.send_idles(LOCK_IDLES)
    await seq.send_ethernet_frame(gold)
    await seq.send_idles(20)

    await drain_and_check(dut, monitor, scoreboard)


@cocotb.test()
async def test_back_to_back_frames(dut):
    seq, monitor, scoreboard = await init_dut(dut)
    seq.scrambler_state = 1

    frames = [
        list(range(64)),
        [0xDE, 0xAD, 0xBE, 0xEF] * 18,
        [0xFF] * 128,
    ]
    for f in frames:
        scoreboard.add_expected(f)

    await seq.send_idles(LOCK_IDLES)
    await seq.send_back_to_back_frames(frames, gap_idles=4)
    await seq.send_idles(20)

    await drain_and_check(dut, monitor, scoreboard)


@cocotb.test()
async def test_frame_lengths(dut):
    seq, monitor, scoreboard = await init_dut(dut)
    seq.scrambler_state = 0

    test_frames = [
        [0xAB],
        [0x11] * 7,
        [0x22] * 8,
        [0x33] * 64,
    ]
    for f in test_frames:
        scoreboard.add_expected(f)

    await seq.send_idles(LOCK_IDLES)
    for frame in test_frames:
        await seq.send_ethernet_frame(frame)
        await seq.send_idles(8)

    await seq.send_idles(20)
    await drain_and_check(dut, monitor, scoreboard)


@cocotb.test()
async def test_lock_loss_recovery(dut):
    seq, monitor, scoreboard = await init_dut(dut)
    seq.scrambler_state = 0

    good_frame = [0xCA, 0xFE, 0xBA, 0xBE] * 16
    scoreboard.add_expected(good_frame)

    await seq.send_idles(LOCK_IDLES)
    await seq.send_corrupted_frame([0xDE] * 32)
    await seq.send_idles(LOCK_IDLES)
    await seq.send_ethernet_frame(good_frame)
    await seq.send_idles(20)

    await drain_and_check(dut, monitor, scoreboard)

    assert scoreboard.bitslip_count > 0 or scoreboard.lock_loss_count > 0, \
        "Expected at least one bitslip or lock-loss event during corruption"


@cocotb.test()
async def test_bubble_insertion(dut):
    seq, monitor, scoreboard = await init_dut(dut)
    seq.scrambler_state = 0

    gold = [0x55] * 64
    scoreboard.add_expected(gold)

    await seq.send_idles(LOCK_IDLES)
    await seq.send_idles(4)
    await seq.send_bubble()
    await seq.send_bubble()
    await seq.send_ethernet_frame(gold)
    await seq.send_bubble()
    await seq.send_bubble()
    await seq.send_idles(20)

    await drain_and_check(dut, monitor, scoreboard)