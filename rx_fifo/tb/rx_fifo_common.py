import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


S_CLK_PERIOD_NS = 2.48139
M_CLK_PERIOD_NS = 4.0


async def initialize_tb(
    dut,
    s_clk_period_ns=S_CLK_PERIOD_NS,
    m_clk_period_ns=M_CLK_PERIOD_NS,
):
    s_clk_gen = Clock(dut.s_clk, s_clk_period_ns, unit="ns")
    m_clk_gen = Clock(dut.m_clk, m_clk_period_ns, unit="ns")
    cocotb.start_soon(s_clk_gen.start())
    cocotb.start_soon(m_clk_gen.start())

    await reset_dut(dut, 2 * max(s_clk_period_ns, m_clk_period_ns))


async def _wait_reset_edges(dut):
    await RisingEdge(dut.s_clk)
    await RisingEdge(dut.s_clk)
    await RisingEdge(dut.m_clk)
    await RisingEdge(dut.m_clk)


async def reset_dut(dut, duration_ns: float = 20):
    if hasattr(dut, "rst"):
        dut.rst.value = 1
        await Timer(duration_ns, unit="ns")
        await _wait_reset_edges(dut)
        dut.rst.value = 0
    elif hasattr(dut, "rst_n"):
        dut.rst_n.value = 1
        await Timer(duration_ns, unit="ns")
        await _wait_reset_edges(dut)
        dut.rst_n.value = 0
    else:
        raise RuntimeError("DUT does not have 'rst' or 'rst_n' signal!")
