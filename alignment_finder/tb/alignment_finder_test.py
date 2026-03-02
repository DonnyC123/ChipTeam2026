import cocotb

from tb_utils.tb_common import initialize_tb
from alignment_finder.tb.alignment_finder_test_base import AlignmentFinderTestBase

# CHANGE THE TESTBASE TO INCLUDE THE REGULAR MODEL INSTEAD OF BAD INPUT
# @cocotb.test()
# async def sanity_test(dut):
#     await initialize_tb(dut, clk_period_ns=10)

#     DATA_W = int(getattr(dut, "DATA_WIDTH", 66)) if hasattr(dut, "DATA_WIDTH") else 66
#     GOOD   = 32
#     BAD    = 8

#     testbase = AlignmentFinderTestBase(
#         dut,
#         data_width=DATA_W,
#         good_count=GOOD,
#         bad_count=BAD,
#     )

#     await testbase.sequence.add_bubble(4)
#     await testbase.sequence.add_control_idle_stream(GOOD + 20, valid=True)
#     await testbase.sequence.add_control_idle_stream(GOOD + 20, valid=True)

#     await testbase.wait_for_driver_done()

#     await testbase.scoreboard.check()

@cocotb.test()
async def bad_header_test(dut):
    await initialize_tb(dut, clk_period_ns=10)

    DATA_W = int(getattr(dut, "DATA_WIDTH", 66)) if hasattr(dut, "DATA_WIDTH") else 66

    testbase = AlignmentFinderTestBase(
        dut,
        data_width=DATA_W,
        good_count=32,
        bad_count=8,
    )

    await testbase.sequence.add_bubble(1)
    await testbase.sequence.add_bad_header_stream(200, valid=True)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()
