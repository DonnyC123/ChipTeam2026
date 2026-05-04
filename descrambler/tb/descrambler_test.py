import cocotb
from cocotb.clock    import Clock
from cocotb.triggers import RisingEdge, ClockCycles

from tb_utils.generic_drivers       import GenericDriver
from tb_utils.abstract_transactions import AbstractTransaction
from tb_utils.generic_monitor       import GenericValidMonitor

from descrambler.tb.descrambler_transaction    import descramblerTransaction
from descrambler.tb.descrambler_sequence_item  import descramblerSequenceItem
from descrambler.tb.descrambler_sequence       import descramblerSequence
from descrambler.tb.descrambler_scoreboard     import descramblerScoreboard

CLK_PERIOD_NS = 10
RESET_CYCLES  = 5
LOCK_IDLES    = 64
FLUSH_CYCLES  = 900

class descramblerPayloadMonitor(GenericValidMonitor):
    async def _monitor(self):
        while True:
            await RisingEdge(self.dut.clk)
            await cocotb.triggers.ReadOnly()

            txn = descramblerTransaction()
            txn.valid_o   = self.dut.valid_o.value
            txn.x_64b_o    = self.dut.x_64b_o.value

            if txn.valid_o:
                self.actual_queue.put_nowait(txn)


async def init_dut(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())

    dut.valid_i.value = 0
    dut.x_64b_i.value  = 0
    dut.rst.value         = 1
    await ClockCycles(dut.clk, RESET_CYCLES)
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    driver     = GenericDriver(dut, descramblerSequenceItem)
    monitor    = descramblerPayloadMonitor(dut, descramblerTransaction)
    cocotb.start_soon(monitor._monitor())
    scoreboard = descramblerScoreboard()
    seq        = descramblerSequence(driver)
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



# descrambler-specific tests
@cocotb.test()
async def test_descrambler_known_pattern(dut):
    """
    Send a known 64b word and header, check output matches expected descrambled value.
    """
    seq, monitor, scoreboard = await init_dut(dut)

    # Example: all ones
    data = 0xFFFFFFFFFFFFFFFF
    await seq.send_word(data)

    # Wait for output
    await ClockCycles(dut.clk, 2)
    await RisingEdge(dut.clk)

    # Check output
    assert monitor.actual_queue.qsize() > 0, "No output from descrambler!"
    txn = monitor.actual_queue.get_nowait()
    # Compute expected descrambled value using the same algorithm as the sequence
    seq.set_state((1 << seq.descrambler_STATE_W) - 1)
    expected = seq.descrambler_64b(data)
    out = int(txn.x_64b_o)
    assert out == expected, f"Descrambled output mismatch: got {out:016X}, expected {expected:016X}"


@cocotb.test()
async def test_descrambler_random_patterns(dut):
    """
    Send several random 64b words and check output matches expected descrambled value.
    """
    import random
    seq, monitor, scoreboard = await init_dut(dut)
    seq.set_state((1 << seq.descrambler_STATE_W) - 1)
    for _ in range(5):
        data = random.getrandbits(64)
        await seq.send_word(data)
        await ClockCycles(dut.clk, 2)
        await RisingEdge(dut.clk)
        assert monitor.actual_queue.qsize() > 0, "No output from descrambler!"
        txn = monitor.actual_queue.get_nowait()
        expected = seq.descramble_64b(data)
        out = int(txn.x_64b_o)
        assert out == expected, f"Random pattern: got {out:016X}, expected {expected:016X}"