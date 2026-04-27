# TX Module

This directory contains the current single-queue DMA-to-PCS TX subsystem.

## Current RTL

The supported FPGA-facing path is in `rtl/`:

- `tx_subsystem_axis_1q.sv`: flat AXI-Stream top-level wrapper with separate DMA and TX clocks.
- `tx_subsystem.sv`: packet-aware 256-bit DMA to 64-bit PCS datapath.
- `tx_async_fifo.sv`: handwritten gray-pointer CDC FIFO.
- `tx_subsystem_pkg.sv`: shared widths and packed FIFO entry type.

Use `filelist/tx_module_1q.f` for the current RTL source list.

## Current Testbench

The supported tests are in `tb/` and target `tx_subsystem_axis_1q` only. They follow the `tb_utils` generic-test pattern with a TX-specific AXIS driver for ready/valid hold semantics.

## Legacy Code

`legacy/multi_queue/` contains the previous queue FIFO and scheduler implementation for reference only. It is not part of the current single-queue CDC path and should not be added to the FPGA source set unless multi-queue support is intentionally revived.n