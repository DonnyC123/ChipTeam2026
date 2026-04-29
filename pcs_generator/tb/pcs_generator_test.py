import random

import cocotb
from cocotb.triggers import RisingEdge
from cocotb.utils import get_sim_time

from pcs_generator.tb.pcs_checker import PCSChecker
from pcs_generator.tb.pcs_drivers import PCSDriver
from pcs_generator.tb.pcs_sequence import PCSSequence
from pcs_generator.tb.pcs_scoreboard import PCSScoreboard
from pcs_generator.tb.pcs_sequence_item import PCSSequenceItem
from pcs_generator.tb.pcs_test_base import PCSTestBase
from tb_utils.tb_common import initialize_tb


def _frame_payload(length: int, *, seed: int) -> bytes:
    return bytes((seed + byte_index) & 0xFF for byte_index in range(length))


class _AcceptedBeatRecorder:
    def __init__(self):
        self.notifications: list[dict[str, int]] = []

    async def notify(self, notification: PCSSequenceItem):
        self.notifications.append(
            {
                "time_ns": int(get_sim_time("ns")),
                "tdata": int(notification.tdata),
                "tkeep": int(notification.tkeep),
                "tlast": int(notification.tlast),
            }
        )


async def _wait_for_notification_count(
    dut, recorder: _AcceptedBeatRecorder, expected_count: int, *, max_cycles: int = 12
):
    for _ in range(max_cycles):
        if len(recorder.notifications) >= expected_count:
            return
        await RisingEdge(dut.clk)

    raise AssertionError(
        f"Timed out waiting for {expected_count} accepted-beat notifications; "
        f"saw {len(recorder.notifications)}"
    )


async def _make_testbase(dut) -> PCSTestBase:
    await initialize_tb(dut, clk_period_ns=10)
    return PCSTestBase(
        dut,
        scoreboard=PCSScoreboard,
        checker=PCSChecker,
    )


async def _add_idle_cycles(sequence: PCSSequence, cycles: int, *, out_ready: int = 1) -> None:
    for _ in range(cycles):
        await sequence.add_idle(tdata=0, tkeep=0, tvalid=0, tlast=0, out_ready=out_ready)


@cocotb.test()
async def manual_single_frame_term_l1_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(64, seed=0x10))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_single_frame_term_l2_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(65, seed=0x11))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_single_frame_term_l3_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(66, seed=0x12))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_single_frame_term_l4_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(67, seed=0x13))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_single_frame_term_l5_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(68, seed=0x14))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_single_frame_term_l6_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(69, seed=0x15))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_single_frame_term_l7_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(70, seed=0x16))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_single_frame_term_l0_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(71, seed=0x17))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_multi_frame_back_to_back_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(64, seed=0x20))
    await testbase.sequence.add_manual_stream(_frame_payload(67, seed=0x30))
    await testbase.sequence.add_manual_stream(_frame_payload(71, seed=0x40))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_multi_frame_idle_separated_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(64, seed=0x50))
    await testbase.sequence.add_idle(tdata=0, tkeep=0, tvalid=0, tlast=0, out_ready=1)
    await testbase.sequence.add_idle(tdata=0, tkeep=0, tvalid=0, tlast=0, out_ready=1)
    await testbase.sequence.add_manual_stream(_frame_payload(68, seed=0x60))
    await testbase.sequence.add_idle(tdata=0, tkeep=0, tvalid=0, tlast=0, out_ready=1)
    await testbase.sequence.add_manual_stream(_frame_payload(71, seed=0x70))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_multi_frame_mixed_gap_pattern_compare_test(dut):
    testbase = await _make_testbase(dut)

    # 2 back-to-back streams
    await testbase.sequence.add_manual_stream(_frame_payload(64, seed=0xA0))
    await testbase.sequence.add_manual_stream(_frame_payload(67, seed=0xB0))

    # 4-idle gap
    for _ in range(4):
        await testbase.sequence.add_idle(tdata=0, tkeep=0, tvalid=0, tlast=0, out_ready=1)

    # One more stream
    await testbase.sequence.add_manual_stream(_frame_payload(68, seed=0xC0))

    # >2-idle gap (use 3)
    for _ in range(3):
        await testbase.sequence.add_idle(tdata=0, tkeep=0, tvalid=0, tlast=0, out_ready=1)

    # Final stream
    await testbase.sequence.add_manual_stream(_frame_payload(71, seed=0xD0))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_single_frame_96b_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(96, seed=0x12))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_single_frame_127b_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(127, seed=0x23))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_multi_frame_all_term_patterns_back_to_back_compare_test(dut):
    testbase = await _make_testbase(dut)

    for payload_len, seed in zip(range(64, 72), range(0x30, 0x38)):
        await testbase.sequence.add_manual_stream(_frame_payload(payload_len, seed=seed))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_multi_frame_long_idle_gap_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(64, seed=0x40))
    await _add_idle_cycles(testbase.sequence, 12, out_ready=1)
    await testbase.sequence.add_manual_stream(_frame_payload(71, seed=0x50))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_multi_frame_staggered_idle_gaps_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(64, seed=0x61))
    await _add_idle_cycles(testbase.sequence, 1, out_ready=1)
    await testbase.sequence.add_manual_stream(_frame_payload(65, seed=0x71))
    await _add_idle_cycles(testbase.sequence, 2, out_ready=1)
    await testbase.sequence.add_manual_stream(_frame_payload(66, seed=0x81))
    await _add_idle_cycles(testbase.sequence, 3, out_ready=1)
    await testbase.sequence.add_manual_stream(_frame_payload(67, seed=0x91))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_multi_frame_min_max_alternating_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(64, seed=0xA1))
    await testbase.sequence.add_manual_stream(_frame_payload(71, seed=0xB1))
    await _add_idle_cycles(testbase.sequence, 2, out_ready=1)
    await testbase.sequence.add_manual_stream(_frame_payload(64, seed=0xC1))
    await testbase.sequence.add_manual_stream(_frame_payload(71, seed=0xD1))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_multi_frame_mixed_input_types_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(_frame_payload(64, seed=0xE1))
    await testbase.sequence.add_manual_stream(bytearray(_frame_payload(68, seed=0xE2)))
    await _add_idle_cycles(testbase.sequence, 3, out_ready=1)
    await testbase.sequence.add_manual_stream(list(_frame_payload(71, seed=0xE3)))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def dirty_stream_min_frame_compare_test(dut):
    random.seed(20260420)
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_dirty_stream(_frame_payload(64, seed=0xF1))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def dirty_stream_term_l0_size_compare_test(dut):
    random.seed(20260421)
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_dirty_stream(_frame_payload(71, seed=0xF2))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def dirty_multi_frame_compare_test(dut):
    random.seed(20260422)
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_dirty_stream(_frame_payload(64, seed=0xF3))
    await _add_idle_cycles(testbase.sequence, 2, out_ready=1)
    await testbase.sequence.add_manual_dirty_stream(_frame_payload(69, seed=0xF4))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_bytearray_stream_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(bytearray(_frame_payload(72, seed=0x80)))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def manual_list_stream_compare_test(dut):
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_stream(list(_frame_payload(73, seed=0x90)))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def dirty_stream_compare_test(dut):
    random.seed(20260419)
    testbase = await _make_testbase(dut)

    await testbase.sequence.add_manual_dirty_stream(_frame_payload(86, seed=0xC0))

    await testbase.wait_for_driver_done()
    await testbase.check_outputs()


@cocotb.test()
async def accepted_beat_notification_contract_test(dut):
    await initialize_tb(dut, clk_period_ns=10)

    driver = PCSDriver(dut=dut, seq_item_type=PCSSequenceItem)
    sequence = PCSSequence(driver=driver)
    recorder = _AcceptedBeatRecorder()
    driver.add_subscriber(recorder)

    first = await sequence.add_axis_transaction(
        tdata=0x0706050403020100,
        tkeep=0xFF,
        tvalid=1,
        tlast=0,
        out_ready=0,
    )
    await sequence.add_idle(
        tdata=0,
        tkeep=0,
        tvalid=0,
        tlast=0,
        out_ready=0,
    )
    second = await sequence.add_axis_transaction(
        tdata=0x0F0E0D0C0B0A0908,
        tkeep=0xFF,
        tvalid=1,
        tlast=1,
        out_ready=0,
    )

    await _wait_for_notification_count(dut, recorder, 1)
    for _ in range(3):
        await RisingEdge(dut.clk)

    assert len(recorder.notifications) == 1
    assert recorder.notifications[0]["tdata"] == int(first.tdata)
    assert await driver.busy()

    second.out_ready = 1

    await _wait_for_notification_count(dut, recorder, 2)
    for _ in range(2):
        await RisingEdge(dut.clk)

    assert [entry["tdata"] for entry in recorder.notifications] == [
        int(first.tdata),
        int(second.tdata),
    ]
    assert not await driver.busy()
