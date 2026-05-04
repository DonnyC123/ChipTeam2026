import cocotb
from cocotb.clock    import Clock
from cocotb.triggers import RisingEdge, ClockCycles

from tb_utils.generic_drivers       import GenericDriver
from tb_utils.abstract_transactions import AbstractTransaction
from tb_utils.generic_monitor       import GenericValidMonitor

from scrambler.tb.scrambler_transaction    import ScramblerTransaction
from scrambler.tb.scrambler_sequence_item  import ScramblerSequenceItem
from scrambler.tb.scrambler_sequence       import ScramblerSequence
from scrambler.tb.scrambler_scoreboard     import ScramblerScoreboard

CLK_PERIOD_NS = 10
RESET_CYCLES  = 5
LOCK_IDLES    = 64
FLUSH_CYCLES  = 900

class ScramblerPayloadMonitor(GenericValidMonitor):
    async def _monitor(self):
        while True:
            await RisingEdge(self.dut.clk)

            txn = ScramblerTransaction()
            txn.valid_o   = self.dut.valid_o.value
            txn.x_66b_o    = self.dut.x_66b_o.value

            if txn.valid:
                self.actual_queue.put_nowait(txn)


async def init_dut(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())

    dut.valid_i.value = 0
    dut.x_64b_i.value  = 0
    dut.x_2b_header_i.value = 0
    dut.rst.value         = 1
    await ClockCycles(dut.clk, RESET_CYCLES)
    dut.rst.value = 0
    await RisingEdge(dut.clk)

    driver     = GenericDriver(dut, ScramblerSequenceItem)
    monitor    = ScramblerPayloadMonitor(dut, ScramblerTransaction)
    scoreboard = ScramblerScoreboard()
    seq        = ScramblerSequence(driver)
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



# Scrambler-specific tests
@cocotb.test()
async def test_scrambler_known_pattern(dut):
    """
    Send a known 64b word and header, check output matches expected scrambled value.
    """
    seq, monitor, scoreboard = await init_dut(dut)

    # Example: all ones
    data = 0xFFFFFFFFFFFFFFFF
    header = 0b01
    await seq.send_word(data, header)

    # Wait for output
    await ClockCycles(dut.clk, 2)
    await RisingEdge(dut.clk)

    # Check output
    assert monitor.actual_queue.qsize() > 0, "No output from scrambler!"
    txn = monitor.actual_queue.get_nowait()
    # Compute expected scrambled value using the same algorithm as the sequence
    seq.set_state((1 << seq.SCRAMBLER_STATE_W) - 1)
    expected = seq.scramble_66b(data, header)
    out = int(txn.x_66b_o)
    assert out == expected, f"Scrambled output mismatch: got {out:016X}, expected {expected:016X}"


@cocotb.test()
async def test_scrambler_random_patterns(dut):
    """
    Send several random 64b words and check output matches expected scrambled value.
    """
    import random
    seq, monitor, scoreboard = await init_dut(dut)
    seq.set_state((1 << seq.SCRAMBLER_STATE_W) - 1)
    for _ in range(5):
        data = random.getrandbits(64)
        header = random.randint(0, 3)
        await seq.send_word(data, header)
        await ClockCycles(dut.clk, 2)
        await RisingEdge(dut.clk)
        assert monitor.actual_queue.qsize() > 0, "No output from scrambler!"
        txn = monitor.actual_queue.get_nowait()
        expected = seq.scramble_66b(data, header)
        out = int(txn.x_66b_o)
        assert out == expected, f"Random pattern: got {out:016X}, expected {expected:016X}"