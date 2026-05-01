import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


S_CLK_PERIOD_PS = 2481
M_CLK_PERIOD_PS = 4000


async def initialize_tb(
    dut,
    s_clk_period_ps=S_CLK_PERIOD_PS,
    m_clk_period_ps=M_CLK_PERIOD_PS,
    phase_seed: int | None = None,
):
    rng = random.Random(phase_seed)
    s_clk_phase_ps = rng.randint(0, s_clk_period_ps - 1)
    m_clk_phase_ps = rng.randint(0, m_clk_period_ps - 1)

    dut._log.info(
        f"Clock phase offsets: s_clk={s_clk_phase_ps}ps, m_clk={m_clk_phase_ps}ps"
    )

    s_clk_gen = Clock(dut.s_clk, s_clk_period_ps, unit="ps")
    m_clk_gen = Clock(dut.m_clk, m_clk_period_ps, unit="ps")

    async def _start_after(delay_ps, clk_gen):
        if delay_ps > 0:
            await Timer(delay_ps, unit="ps")
        await clk_gen.start()

    cocotb.start_soon(_start_after(s_clk_phase_ps, s_clk_gen))
    cocotb.start_soon(_start_after(m_clk_phase_ps, m_clk_gen))

    reset_duration_ns = 2 * max(s_clk_period_ps, m_clk_period_ps) / 1000
    await reset_dut(dut, reset_duration_ns)


async def _wait_reset_edges(dut):
    await RisingEdge(dut.s_clk)
    await RisingEdge(dut.s_clk)
    await RisingEdge(dut.m_clk)
    await RisingEdge(dut.m_clk)


async def reset_dut(dut, duration_ns: float = 20):
    if hasattr(dut, "s_rst") and hasattr(dut, "m_rst"):
        dut.s_rst.value = 1
        dut.m_rst.value = 1
        await Timer(duration_ns, unit="ns")
        await _wait_reset_edges(dut)
        dut.s_rst.value = 0
        dut.m_rst.value = 0
    elif hasattr(dut, "rst"):
        dut.rst.value = 1
        await Timer(duration_ns, unit="ns")
        await _wait_reset_edges(dut)
        dut.rst.value = 0
    elif hasattr(dut, "rst_n"):
        dut.rst_n.value = 0
        await Timer(duration_ns, unit="ns")
        await _wait_reset_edges(dut)
        dut.rst_n.value = 1
    else:
        raise RuntimeError("DUT does not have 'rst', 'rst_n', or 's_rst'/'m_rst' signals!")
