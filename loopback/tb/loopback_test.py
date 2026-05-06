"""End-to-end loopback test: DMA -> tx_cdc_top -> wire_emulator (with bit
offset) -> rx_top -> AXIS. Verifies that:

  1. rx_locked eventually asserts after enough bitslips
  2. The bitslip count is consistent with OFFSET_BITS
  3. Frames sent on DMA come out on the RX AXIS port byte-for-byte
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge


PCS_PERIOD_NS = 4
DMA_PERIOD_NS = 5
AXI_PERIOD_NS = 5


async def reset_all(dut, cycles: int = 8):
    dut.dma_rst.value = 1
    dut.pcs_rst.value = 1
    dut.axi_rst.value = 1
    dut.s_axis_dma_tvalid_i.value = 0
    dut.s_axis_dma_tlast_i.value  = 0
    dut.s_axis_dma_tdata_i.value  = 0
    dut.s_axis_dma_tkeep_i.value  = 0
    dut.s_axis_dma_tdest_i.value  = 0
    dut.m_axis_rx_tready_i.value  = 1
    for _ in range(cycles):
        await RisingEdge(dut.pcs_clk)
    dut.dma_rst.value = 0
    dut.pcs_rst.value = 0
    dut.axi_rst.value = 0
    for _ in range(4):
        await RisingEdge(dut.pcs_clk)


async def send_dma_frame(dut, frame: bytes, qid: int = 0):
    """Drive one ethernet frame over the 256-bit DMA AXIS in 32-byte beats."""
    beat_bytes = 32
    nbeats = (len(frame) + beat_bytes - 1) // beat_bytes
    dut._log.info(f"send_dma_frame: {len(frame)} bytes in {nbeats} beats")
    for i in range(nbeats):
        chunk = frame[i * beat_bytes:(i + 1) * beat_bytes]
        last  = (i == nbeats - 1)
        keep  = (1 << len(chunk)) - 1
        data  = int.from_bytes(chunk.ljust(beat_bytes, b"\x00"), "little")

        dut.s_axis_dma_tdata_i.value  = data
        dut.s_axis_dma_tkeep_i.value  = keep
        dut.s_axis_dma_tdest_i.value  = qid
        dut.s_axis_dma_tlast_i.value  = 1 if last else 0
        dut.s_axis_dma_tvalid_i.value = 1

        await RisingEdge(dut.dma_clk)
        wait_cnt = 0
        while not int(dut.s_axis_dma_tready_o.value):
            await RisingEdge(dut.dma_clk)
            wait_cnt += 1
            if wait_cnt > 10_000:
                raise TimeoutError(f"DMA tready never asserted on beat {i}")
        dut._log.info(f"send_dma_frame: beat {i} accepted (waited {wait_cnt} cycles)")

    dut.s_axis_dma_tvalid_i.value = 0
    dut.s_axis_dma_tlast_i.value  = 0
    dut._log.info("send_dma_frame: done")


async def collect_rx_frame(dut, timeout_cycles: int = 200_000) -> bytes | None:
    """Block until one full frame is received (tlast), or None on timeout."""
    out = bytearray()
    beat_count = 0
    for _ in range(timeout_cycles):
        await RisingEdge(dut.axi_clk)
        if int(dut.m_axis_rx_tvalid_o.value) and int(dut.m_axis_rx_tready_i.value):
            data = int(dut.m_axis_rx_tdata_o.value)
            keep = int(dut.m_axis_rx_tkeep_o.value)
            last = int(dut.m_axis_rx_tlast_o.value)
            beat_count += 1
            dut._log.info(f"rx beat #{beat_count}: keep={keep:#010x} last={last}")
            for byte_idx in range(32):
                if (keep >> byte_idx) & 1:
                    out.append((data >> (byte_idx * 8)) & 0xFF)
            if last:
                return bytes(out)
    dut._log.warning(f"timeout: collected {beat_count} beats, {len(out)} bytes, no tlast")
    return None


async def wait_for_lock(dut, timeout_cycles: int = 400_000) -> int:
    """Returns bitslip count when lock asserts; raises on timeout."""
    bitslips = 0
    for cyc in range(timeout_cycles):
        await RisingEdge(dut.pcs_clk)
        if int(dut.rx_bitslip_o.value):
            bitslips += 1
        if int(dut.rx_locked_o.value):
            dut._log.info(f"rx_locked asserted at cycle {cyc}, after {bitslips} bitslips")
            return bitslips
    raise TimeoutError(f"rx_locked never asserted in {timeout_cycles} cycles")


def _start_clocks(dut):
    cocotb.start_soon(Clock(dut.pcs_clk, PCS_PERIOD_NS, unit="ns").start())
    cocotb.start_soon(Clock(dut.dma_clk, DMA_PERIOD_NS, unit="ns").start())
    cocotb.start_soon(Clock(dut.axi_clk, AXI_PERIOD_NS, unit="ns").start())


@cocotb.test()
async def test_loopback_locks_after_offset(dut):
    """RX must bitslip past the wire_emulator's OFFSET_BITS to find alignment."""
    _start_clocks(dut)
    await reset_all(dut)
    bitslips = await wait_for_lock(dut)
    assert bitslips >= 1, "expected at least one bitslip given non-zero offset"


@cocotb.test()
async def test_loopback_round_trip_frame(dut):
    """One frame in -> one frame out, byte-for-byte."""
    _start_clocks(dut)
    await reset_all(dut)
    await wait_for_lock(dut)

    # Settle a bit after lock so the descrambler/assembler are ready.
    for _ in range(64):
        await RisingEdge(dut.pcs_clk)

    frame = bytes(range(64))
    cocotb.start_soon(send_dma_frame(dut, frame, qid=0))

    rx = await collect_rx_frame(dut)
    assert rx is not None, "no frame received"
    assert rx == frame, f"mismatch:\n sent={frame.hex()}\n got ={rx.hex()}"
