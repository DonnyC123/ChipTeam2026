import cocotb
from cocotb.triggers import RisingEdge

from tb_utils.tb_common import initialize_tb
from tb_utils.generic_monitor import GenericMonitor
from tb_utils.generic_drivers import GenericDriver
from alignment_finder.tb.alignment_finder_transaction import AlignmentFinderOutTransaction
from alignment_finder.tb.alignment_finder_sequence import AlignmentFinderSequence
from alignment_finder.tb.alignment_finder_sequence_item import AlignmentFinderSequenceItem

async def wait_cycles(dut, n):
    for _ in range(n):
        await RisingEdge(dut.clk)

async def get_monitor(monitor, n):
    a = []
    for i in range(n):
        a.append(await monitor.actual_queue.get())
    return a

def all_locked(a, value):
    for i, (locked, bitslip) in enumerate(a):
        if locked != value:
            raise AssertionError(f"expected locked_o")
        
def any_locked(a, value):
    if not any(locked == value for locked, bitslip in a):
        raise AssertionError(f"never observed locked_o")

@cocotb.test()
async def lock_test(dut):
    await initialize_tb(dut, clk_period_ns=10)

    # driver and sequence
    good_count = int(dut.GOOD_COUNT.value)
    bad_count = int(dut.BAD_COUNT.value)
    driver = GenericDriver(dut, AlignmentFinderSequenceItem)
    sequence = AlignmentFinderSequence(driver)
    monitor = GenericMonitor(dut, AlignmentFinderOutTransaction)

    # sends some bubbles and makes sure locked isn't high
    await sequence.add_bubble(3)
    await wait_cycles(dut, 2)
    a = await get_monitor(monitor, 3)
    all_locked(a, 0)

    # sends a sequence of good packets
    await sequence.add_control_idle_stream(good_count + 5, valid=True)
    a = await get_monitor(monitor, good_count + 5)
    any_locked(a, 1)

    # valid data stops but locked o should be high
    await sequence.add_bubble(3)
    a = await get_monitor(monitor, 3)
    all_locked(a, 1)

    # bad headers
    await sequence.add_bad_header_stream(bad_count + 3, valid=True)
    a = await get_monitor(monitor, bad_count + 3)
    any_locked(a, 0)
