import cocotb
from multiplier_demo.tb.fast_mutliplier_test_base import FastMultiplierTestBase
from tb_utils.tb_common import initialize_tb


@cocotb.test()
async def sanity_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    testbase = FastMultiplierTestBase(dut)
    await testbase.sequence.add_multiplication_op(10, 12)

    await testbase.wait_for_driver_done()
