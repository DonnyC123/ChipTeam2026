import random

import cocotb

from pcs_generator.tb.pcs_test_base import PCSTestBase
from tb_utils.generic_checker import GenericChecker
from tb_utils.generic_scoreboard import GenericScoreboard
from tb_utils.tb_common import initialize_tb


def _frame_payload(length: int, *, seed: int) -> bytes:
    return bytes((seed + byte_index) & 0xFF for byte_index in range(length))


async def _make_testbase(dut) -> PCSTestBase:
    await initialize_tb(dut, clk_period_ns=10)
    return PCSTestBase(
        dut,
        scoreboard=GenericScoreboard,
        checker=GenericChecker,
    )


@cocotb.test()
async def single_clean_frame_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(70, seed=0x10))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def multi_frame_idle_separated_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(64, seed=0x20))
    await testbase.sequence.add_idle(tdata=0, tkeep=0, tvalid=0, tlast=0, out_ready=1)
    await testbase.sequence.add_idle(tdata=0, tkeep=0, tvalid=0, tlast=0, out_ready=1)
    await testbase.sequence.add_manual_stream(_frame_payload(78, seed=0x80))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def dirty_stream_compare_test(dut):
    random.seed(20260419)
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_dirty_stream(_frame_payload(86, seed=0xC0))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()
