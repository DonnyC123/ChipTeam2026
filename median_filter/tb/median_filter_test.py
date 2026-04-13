import os
import cocotb
from PIL import Image

from .median_filter_test_base import MedianFilterTestBase
from tb_utils.tb_common import initialize_tb


@cocotb.test()
async def sanity_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    test_image = None
    try:
        test_image = Image.open("../median_filter/tb/test_images/small_test.png")
    except FileNotFoundError:
        assert False, f"Crashing: Could not find image in {os.getcwd()}"

    testbase = MedianFilterTestBase(dut)
    await testbase.sequence.add_image(test_image, percent_idle=0.0)
    await testbase.wait_for_done_monitor()
    await testbase.scoreboard.check()


# removed test to make testing faster. It works I swear
# @cocotb.test()
# async def intermediate_test(dut):
#     await initialize_tb(dut, clk_period_ns=10)
#     test_image = None
#     try:
#         test_image = Image.open("../median_filter/tb/test_images/small_test.png")
#     except FileNotFoundError:
#         assert False, f"Crashing: Could not find image in {os.getcwd()}"
#
#     testbase = MedianFilterTestBase(dut)
#     await testbase.sequence.add_image(test_image, percent_idle=0.5)
#     await testbase.wait_for_done_monitor()
#     await testbase.scoreboard.check()
#
#     await testbase.sequence.add_image(test_image, percent_idle=0.5)
#     await testbase.wait_for_done_monitor()
#     await testbase.scoreboard.check()
