import random

import cocotb
from cocotb.triggers import RisingEdge

from tb.tx_subsystem_test_base import TxSubsystemTestBase
from tb_utils.tb_common import initialize_tb


@cocotb.test()
async def tx_subsystem_axis_basic_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSubsystemTestBase(dut)

    words = [
        (
            0x_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111_1111,
            0xFFFF_FFFF,
            0,
        ),
        (
            0x_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222_2222,
            0x0FFF_FFFF,
            0,
        ),
        (
            0x_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333_3333,
            0x00FF_00FF,
            1,
        ),
    ]

    for data, keep, last in words:
        await testbase.sequence.add_dma_axis_word(
            data=data,
            keep=keep,
            last=last,
            q_valid=0,
            q_last=0,
            dma_req_ready=1,
            m_axis_tready=1,
        )

    await testbase.sequence.add_idle(cycles=len(words) * 8, m_axis_tready=1)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_subsystem_axis_long_random_test(dut):
    await initialize_tb(dut, clk_period_ns=10)
    testbase = TxSubsystemTestBase(dut)

    rng = random.Random(0x7522_2026)
    num_words = 64

    for idx in range(num_words):
        data = rng.getrandbits(256)
        keep = rng.getrandbits(32)
        last = 1 if idx == (num_words - 1) else 0
        await testbase.sequence.add_dma_axis_word(
            data=data,
            keep=keep,
            last=last,
            q_valid=0,
            q_last=0,
            dma_req_ready=1,
            m_axis_tready=1,
        )
        # One DMA word expands to 4 PCS beats, so pace injection to avoid
        # overdriving the AXIS ingress beyond sustainable throughput.
        await testbase.sequence.add_idle(cycles=3, m_axis_tready=1)

    await testbase.sequence.add_idle(cycles=num_words * 4, m_axis_tready=1)

    await testbase.wait_for_driver_done()
    await testbase.scoreboard.check()


@cocotb.test()
async def tx_subsystem_dma_req_ready_gating_test(dut):
    await initialize_tb(dut, clk_period_ns=10)

    dut.s_axis_dma_tdata_i.value = 0
    dut.s_axis_dma_tkeep_i.value = 0
    dut.s_axis_dma_tvalid_i.value = 0
    dut.s_axis_dma_tlast_i.value = 0
    dut.dma_data_i.value = 0
    dut.dma_valid_i.value = 0
    dut.m_axis_tready_i.value = 1
    dut.q_valid_i.value = 0b01
    dut.q_last_i.value = 0b01

    dut.dma_req_ready_i.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
        assert int(dut.dma_read_en_o.value) == 0, "dma_read_en_o should stay low when dma_req_ready_i=0"

    dut.dma_req_ready_i.value = 1
    seen_read = False
    for _ in range(5):
        await RisingEdge(dut.clk)
        if int(dut.dma_read_en_o.value):
            seen_read = True
            break

    assert seen_read, "dma_read_en_o should assert when dma_req_ready_i goes high"
