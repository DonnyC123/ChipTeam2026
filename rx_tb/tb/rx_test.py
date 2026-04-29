# rx_test.py
import cocotb
from cocotb.clock    import Clock
from cocotb.triggers import RisingEdge, ClockCycles

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
FLUSH_CYCLES  = 900

class PayloadMonitor(GenericValidMonitor):
    async def _monitor(self):
        while True:
            await RisingEdge(self.dut.clk)

            txn = RxTransaction()
            txn.valid_o = self.dut.valid_o.value
            txn.data_o  = self.dut.data_o.value
            txn.mask_o  = self.dut.mask_o.value
            txn.send_o  = self.dut.send_o.value
            txn.drop_o  = self.dut.drop_o.value

            if txn.valid:
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
    await ClockCycles(dut.clk, cycles)
    await RisingEdge(dut.clk)

    while not monitor.actual_queue.empty():
        txn = monitor.actual_queue.get_nowait()
        scoreboard.ingest(txn)

    scoreboard.check_all_received()
    scoreboard.flush()
    # dut._log.info(scoreboard.summary())


@cocotb.test()
async def test_lock_and_single_frame(dut):
    seq, monitor, scoreboard = await init_dut(dut)

    gold = [0xAA, 0xBB, 0xCC, 0xDD] * 16
    scoreboard.add_expected(gold)

    await seq.send_idles(LOCK_IDLES)
    await seq.send_ethernet_frame(gold)
    await seq.send_idles(20)

    await drain_and_check(dut, monitor, scoreboard)


@cocotb.test()
async def test_back_to_back_frames(dut):
    seq, monitor, scoreboard = await init_dut(dut)

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
async def test_invalid_blocks_ignored(dut):
    seq, monitor, scoreboard = await init_dut(dut)

    good_frame = [0xCA, 0xFE, 0xBA, 0xBE] * 16
    scoreboard.add_expected(good_frame)

    await seq.send_idles(20)
    await seq.send_invalid_blocks(20)
    await seq.send_idles(20)
    await seq.send_ethernet_frame(good_frame)
    await seq.send_idles(20)
    await drain_and_check(dut, monitor, scoreboard)

    assert scoreboard.match_count == 1
    assert scoreboard.error_count == 0

@cocotb.test()
async def enforce_12_idles(dut):
    seq, monitor, scoreboard = await init_dut(dut)

    good_frame = [0xCA, 0xFE, 0xBA, 0xBE] * 16
    # scoreboard.add_expected(good_frame)

    await seq.send_idles(5)
    await seq.send_ethernet_frame(good_frame)
    await seq.send_idles(5)
    await drain_and_check(dut, monitor, scoreboard)
