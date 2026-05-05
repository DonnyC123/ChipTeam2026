"""End-to-end loopback test: DMA -> tx_cdc_top -> wire_emulator (with bit
offset) -> rx_top -> AXIS. Verifies that:

  1. rx_locked eventually asserts after enough bitslips
  2. The bitslip count is consistent with OFFSET_BITS
  3. Frames sent on DMA come out on the RX AXIS port byte-for-byte
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly


PCS_PERIOD_NS = 4   # 250 MHz, close enough to GT user clock for sim
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
    for i in range(nbeats):
        chunk = frame[i * beat_bytes:(i + 1) * beat_bytes]
        last  = (i == nbeats - 1)
        keep  = (1 << len(chunk)) - 1
        # AXIS data is little-endian byte 0 in low bits
        data  = int.from_bytes(chunk.ljust(beat_bytes, b"\x00"), "little")

        dut.s_axis_dma_tdata_i.value  = data
        dut.s_axis_dma_tkeep_i.value  = keep
        dut.s_axis_dma_tdest_i.value  = qid
        dut.s_axis_dma_tlast_i.value  = 1 if last else 0
        dut.s_axis_dma_tvalid_i.value = 1

        while True:
            await RisingEdge(dut.dma_clk)
            await ReadOnly()
            if int(dut.s_axis_dma_tready_o.value):
                break

        dut.s_axis_dma_tvalid_i.value = 0
        dut.s_axis_dma_tlast_i.value  = 0


async def collect_rx_frame(dut, timeout_cycles: int = 200_000) -> bytes | None:
    """Block until one full frame is received (tlast), or None on timeout."""
    out = bytearray()
    for _ in range(timeout_cycles):
        await RisingEdge(dut.axi_clk)
        await ReadOnly()
        if int(dut.m_axis_rx_tvalid_o.value) and int(dut.m_axis_rx_tready_i.value):
            data = int(dut.m_axis_rx_tdata_o.value)
            keep = int(dut.m_axis_rx_tkeep_o.value)
            last = int(dut.m_axis_rx_tlast_o.value)
            for byte_idx in range(32):
                if (keep >> byte_idx) & 1:
                    out.append((data >> (byte_idx * 8)) & 0xFF)
            if last:
                return bytes(out)
    return None


async def wait_for_lock(dut, timeout_cycles: int = 200_000) -> int:
    """Returns cycle count it took to lock; raises on timeout."""
    bitslips = 0
    for cyc in range(timeout_cycles):
        await RisingEdge(dut.pcs_clk)
        await ReadOnly()
        if int(dut.rx_bitslip_o.value):
            bitslips += 1
        if int(dut.rx_locked_o.value):
            dut._log.info(f"rx_locked asserted at cycle {cyc}, after {bitslips} bitslips")
            return bitslips
    raise TimeoutError(f"rx_locked never asserted in {timeout_cycles} cycles")


@cocotb.test()
async def test_loopback_locks_after_offset(dut):
    """RX must bitslip past the wire_emulator's OFFSET_BITS to find alignment."""
    cocotb.start_soon(Clock(dut.pcs_clk, PCS_PERIOD_NS, units="ns").start())
    cocotb.start_soon(Clock(dut.dma_clk, DMA_PERIOD_NS, units="ns").start())
    cocotb.start_soon(Clock(dut.axi_clk, AXI_PERIOD_NS, units="ns").start())

    await reset_all(dut)

    # The TX runs idle blocks continuously when no DMA traffic — those
    # idle blocks are what RX uses to find block lock.
    bitslips = await wait_for_lock(dut, timeout_cycles=400_000)
    assert bitslips >= 1, "expected at least one bitslip given non-zero offset"


@cocotb.test()
async def test_loopback_round_trip_frame(dut):
    """One frame in -> one frame out, byte-for-byte."""
    cocotb.start_soon(Clock(dut.pcs_clk, PCS_PERIOD_NS, units="ns").start())
    cocotb.start_soon(Clock(dut.dma_clk, DMA_PERIOD_NS, units="ns").start())
    cocotb.start_soon(Clock(dut.axi_clk, AXI_PERIOD_NS, units="ns").start())

    await reset_all(dut)
    await wait_for_lock(dut, timeout_cycles=400_000)

    # Wait a bit after lock so the descrambler/assembler are settled.
    for _ in range(64):
        await RisingEdge(dut.pcs_clk)

    frame = bytes(range(64))   # 64 bytes, deterministic content
    cocotb.start_soon(send_dma_frame(dut, frame, qid=0))

    rx = await collect_rx_frame(dut, timeout_cycles=400_000)
    assert rx is not None, "no frame received"
    assert rx == frame, f"mismatch:\n sent={frame.hex()}\n got ={rx.hex()}"
